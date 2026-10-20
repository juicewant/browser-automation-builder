import pandas as pd
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import threading
import time


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_safe_xpath_string(text):
    """Return an XPath-safe quoted literal, handling all embedded quote combos."""
    if "'" in text and '"' in text:
        parts = text.split("'")
        return "concat('" + "', \"'\", '".join(parts) + "')"
    elif "'" in text:
        return f'"{text}"'
    return f"'{text}'"


# ── JS: search all frames from current window, return index path ──────────────
_JS_FIND_FRAME_INDEX = """
(function(xpath) {
    function queryXPath(doc) {
        try {
            var r = doc.evaluate(xpath, doc, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            return r.singleNodeValue ? true : false;
        } catch(e) { return false; }
    }
    function searchWindow(win, path) {
        try {
            if (queryXPath(win.document)) return path;
            for (var i = 0; i < win.frames.length; i++) {
                try {
                    var result = searchWindow(win.frames[i], path.concat([i]));
                    if (result !== null) return result;
                } catch(e) {}
            }
        } catch(e) {}
        return null;
    }
    return searchWindow(window, []);
})(arguments[0]);
"""

# ── JS: Dynamic SAP form submit ───────────────────────────────────────────────
_JS_SAP_DYNAMIC_SUBMIT = """
(function(xpath) {
    function queryXPath(win, xpath) {
        try {
            var r = win.document.evaluate(xpath, win.document, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            return r.singleNodeValue || null;
        } catch(e) { return null; }
    }
    function findElement(win) {
        try {
            var el = queryXPath(win, xpath);
            if (el) return { el: el, doc: win.document };
            for (var i = 0; i < win.frames.length; i++) {
                try {
                    var found = findElement(win.frames[i]);
                    if (found) return found;
                } catch(e) {}
            }
        } catch(e) {}
        return null;
    }

    var found = findElement(window);
    if (!found) return 'ERROR:element_not_found';

    var el  = found.el;
    var doc = found.doc;
    var elementId = el.id || '';
    if (!elementId) return 'ERROR:element_has_no_id';

    var form = null;
    var allForms = doc.getElementsByTagName('form');
    if (allForms.length > 0) form = allForms[0];

    if (!form) {
        function findForm(win, ids) {
            for (var i = 0; i < ids.length; i++) {
                try {
                    var f = win.document.getElementById(ids[i]);
                    if (f) return { form: f, doc: win.document };
                } catch(e) {}
            }
            for (var j = 0; j < win.frames.length; j++) {
                try {
                    var r = findForm(win.frames[j], ids);
                    if (r) return r;
                } catch(e) {}
            }
            return null;
        }
        var fr = findForm(window, ['myFormId','crmUIHostDialogContainerForm']);
        if (fr) { form = fr.form; doc = fr.doc; }
    }
    if (!form) return 'ERROR:form_not_found';

    function setField(name, val) {
        var f = doc.getElementById(name) || doc.querySelector('[name="'+name+'"]');
        if (f) f.value = val;
    }
    setField('htmlbevt_ty',   'click');
    setField('htmlbevt_oid',  elementId);
    setField('htmlbevt_id',   'thtmlb:link:click:0');
    setField('htmlbevt_cnt',  '0');
    setField('htmlbevt_par1', '');
    setField('htmlbevt_par2', '');
    form.submit();
    return 'OK:' + elementId;
})(arguments[0]);
"""

# ── JS: Inspector XPath builder ───────────────────────────────────────────────
# Taken directly from the working code's smartXPath logic.
# Key rule: NEVER use @id — SAP IDs are dynamic every session.
# Priority: @title → visible text → DOM path
_JS_INSPECTOR = r"""
(function() {
    if (window.__sapPickH) {
        document.removeEventListener('mousedown', window.__sapPickH, true);
    }

    function smartXPath(el) {
        if (!el || el.nodeType !== 1) return '';
        var tag = el.tagName.toLowerCase();

        // Priority 1: @title — SAP's stable label attribute
        var title = (el.getAttribute('title') || '').trim();
        if (title.length > 0) {
            return '//' + tag + '[contains(@title, \'' +
                   title.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + '\')]';
        }

        // Priority 2: visible inner text (≤50 chars) for interactive elements
        var interactives = ['button','a','span','div','td','th','li','input'];
        if (interactives.indexOf(tag) !== -1) {
            var raw = (el.innerText || el.textContent || '').trim();
            if (raw.length > 0 && raw.length <= 50) {
                return '//*[normalize-space(text())=\'' +
                       raw.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + '\']';
            }
        }

        // Priority 3: relative DOM path — no @id used
        var parts = [];
        var node = el;
        while (node && node.nodeType === 1 && node.tagName.toLowerCase() !== 'html') {
            var t = node.tagName.toLowerCase();
            var idx = 1;
            var total = 0;
            var cur = node.previousSibling;
            var sib = node.parentNode ? node.parentNode.firstChild : null;
            while (cur) {
                if (cur.nodeType === 1 && cur.tagName === node.tagName) idx++;
                cur = cur.previousSibling;
            }
            while (sib) {
                if (sib.nodeType === 1 && sib.tagName === node.tagName) total++;
                sib = sib.nextSibling;
            }
            parts.unshift(total > 1 ? t + '[' + idx + ']' : t);
            node = node.parentNode;
        }
        return '//' + parts.join('/');
    }

    window.__sapPickH = function(e) {
        e.stopImmediatePropagation();
        e.preventDefault();
        document.removeEventListener('mousedown', window.__sapPickH, true);
        var xpath = smartXPath(e.target);
        // 50ms delay lets SAP's handlers bail before the alert fires
        setTimeout(function() { alert('__SAP_XPATH__' + xpath); }, 50);
    };

    document.addEventListener('mousedown', window.__sapPickH, true);
})();
"""


class AutomationEngine:
    def __init__(self, log_callback, status_callback, row_update_callback, capture_callback):
        self.driver            = None
        self.is_running        = False
        self.is_inspecting     = False
        self.report_data       = []
        self.platform          = "SAP"
        self.log               = log_callback
        self.set_ui_status     = status_callback
        self.update_ui_row     = row_update_callback
        self.on_xpath_captured = capture_callback

    def set_platform(self, platform):
        self.platform = platform
        self.log(f"🔄 Platform set to: {platform}")

    # ══════════════════════════════════════════════════════════════════════════
    # BROWSER
    #
    # KEY FIX — the 3 CORS-killing flags from the working code:
    #   --disable-web-security
    #   --disable-site-isolation-trials
    #   --disable-features=IsolateOrigins,site-per-process
    #
    # WITHOUT these, the browser enforces cross-origin isolation even when
    # document.domain is set. Every JS cross-frame access silently returns
    # null or throws a security exception — caught by our try/catch — making
    # it look like elements don't exist when they actually do.
    # The working code calls these the "CORS Killer" and it is the single
    # most important fix that makes SAP frame penetration work.
    # ══════════════════════════════════════════════════════════════════════════
    def launch_browser(self, url, block_resources=True):
        try:
            o = Options()
            o.add_experimental_option("detach", True)

            # ── CORS Killer (from working code) ────────────────────────────
            # These three flags disable Edge's cross-origin isolation so JS
            # running in any frame can freely access sibling/parent frames.
            # Without them, SAP's nested iframes are completely opaque to JS.
            o.add_argument("--disable-web-security")
            o.add_argument("--disable-site-isolation-trials")
            o.add_argument("--disable-features=IsolateOrigins,site-per-process")

            if block_resources:
                prefs = {
                    "profile.managed_default_content_settings.images":       2,
                    "profile.managed_default_content_settings.fonts":        2,
                    "profile.managed_default_content_settings.media_stream": 2,
                }
                o.add_experimental_option("prefs", prefs)
                self.log("🚫 Resource blocking ON — images & fonts disabled.")

            self.driver = webdriver.Edge(options=o)
            self.driver.get(url)
            self.log(f"🌐 Browser launched ({self.platform} mode) — CORS isolation disabled.")
            self.set_ui_status(browser_open=True)
        except Exception as e:
            self.log(f"⚠️ Launch failed: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # INSPECTOR
    #
    # KEY FIX — two changes from the working code:
    #
    # 1. Uses alert() bridge instead of hidden input + postMessage.
    #    Alerts are truly global — they pierce ALL frame boundaries including
    #    cross-origin ones. Our old postMessage approach was blocked when the
    #    click happened inside a restricted inner frame.
    #
    # 2. Injects JS into EVERY frame using Selenium's switch_to.frame() loop
    #    (same as the working code's inject_recursively). This guarantees the
    #    mousedown handler is active in every frame, not just the top level.
    #
    # 3. XPath never uses @id — uses @title → text → DOM path instead.
    # ══════════════════════════════════════════════════════════════════════════
    def toggle_inspector(self):
        if not self.driver:
            self.log("⚠️ Open the browser first!")
            return
        self._start_inspector() if not self.is_inspecting else self.stop_inspecting()

    def _start_inspector(self):
        self.is_inspecting = True
        self.set_ui_status(inspecting=True)
        self.log("🎯 Inspector active — click any element in the browser.")
        threading.Thread(target=self._inspector_worker, daemon=True).start()

    def _inspector_worker(self):
        """
        Injects the mousedown handler into every reachable frame using
        Selenium frame switching (same technique as the working code).
        Then waits for the alert() bridge to fire.
        """
        try:
            # Step 1: Reset to top-level
            self.driver.switch_to.default_content()

            # Step 2: Recursively inject into every frame
            self._inject_inspector_recursive()
            self.driver.switch_to.default_content()

            # Step 3: Wait for alert (up to 30s)
            alert = WebDriverWait(self.driver, 30).until(EC.alert_is_present())
            alert_text = alert.text
            alert.dismiss()

            if alert_text and alert_text.startswith("__SAP_XPATH__"):
                xpath = alert_text[len("__SAP_XPATH__"):].strip()
                self.on_xpath_captured(xpath)
                self.log(f"🎯 Captured: {xpath}")
            else:
                self.log("⚠️ Inspector: unexpected alert dismissed.")

        except Exception as e:
            if self.is_inspecting:
                self.log(f"⚠️ Inspector error: {str(e)[:80]}")
        finally:
            self.stop_inspecting()

    def _inject_inspector_recursive(self):
        """Inject JS mousedown handler into current frame and all child frames."""
        try:
            self.driver.execute_script(_JS_INSPECTOR)
        except Exception:
            pass
        try:
            frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return
        for frame in frames:
            try:
                self.driver.switch_to.frame(frame)
                self._inject_inspector_recursive()
                self.driver.switch_to.parent_frame()
            except Exception:
                try:
                    self.driver.switch_to.parent_frame()
                except Exception:
                    self.driver.switch_to.default_content()

    def stop_inspecting(self):
        self.is_inspecting = False
        self.set_ui_status(inspecting=False)
        try:
            self.driver.execute_script(
                "if(window.__sapPickH){"
                "document.removeEventListener('mousedown',window.__sapPickH,true);"
                "window.__sapPickH=null;}"
                "document.body.style.cursor='default';"
            )
        except:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN EXECUTION LOOP
    # ══════════════════════════════════════════════════════════════════════════
    def execute_sequence(self, excel_path, sheet_name, start_row, steps, global_speed, visual_debug):
        self.is_running  = True
        self.report_data = []
        self.set_ui_status(running=True)
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            for index in range(start_row, len(df)):
                if not self.is_running:
                    break
                row = df.iloc[index]
                self.update_ui_row(index + 1)
                try:
                    for step in steps:
                        if not self.is_running:
                            break
                        self._process_step(step, row, global_speed, visual_debug)
                    self.report_data.append({"Row": index + 1, "Status": "Success"})
                except Exception as e:
                    self.log(f"⚠️ Row {index + 1} failed: {str(e)[:120]}")
                    self.report_data.append({"Row": index + 1, "Status": "Failed", "Error": str(e)})
        except Exception as e:
            self.log(f"🛑 Engine error: {e}")
        finally:
            self.is_running = False
            self.set_ui_status(running=False)

    # ══════════════════════════════════════════════════════════════════════════
    # STEP PROCESSOR
    # ══════════════════════════════════════════════════════════════════════════
    def _process_step(self, step, row, global_speed, visual_debug):
        action = step['action']
        target = step['element']
        delay  = step['delay'] if step['delay'] > 0 else global_speed

        if action == "Wait (Custom)":
            end = time.time() + (float(target) if target else delay)
            while time.time() < end:
                if not self.is_running:
                    return
                time.sleep(0.2)
            return

        if action == "Wait for Loading (Action)":
            self._wait_for_page_ready(timeout=45)
            return

        if action == "SAP Form Submit":
            self._wait_for_page_ready()
            xpath = self._build_xpath(target, row, action, step)
            self._sap_dynamic_submit(xpath)
            time.sleep(delay)
            return

        self._wait_for_page_ready()
        xpath = self._build_xpath(target, row, action, step)
        el    = self._find_element(xpath, timeout=20)

        if el is None:
            raise Exception(f"Element not found: '{target}'")

        if visual_debug:
            try:
                self.driver.execute_script("arguments[0].style.outline='3px solid #FF00FF';", el)
                time.sleep(0.2)
                self.driver.execute_script("arguments[0].style.outline='';", el)
            except:
                pass

        self._dispatch_action(action, el, step, row)
        time.sleep(delay)

    # ══════════════════════════════════════════════════════════════════════════
    # SAP DYNAMIC FORM SUBMIT
    # ══════════════════════════════════════════════════════════════════════════
    def _sap_dynamic_submit(self, xpath):
        self.driver.switch_to.default_content()
        try:
            result = self.driver.execute_script(_JS_SAP_DYNAMIC_SUBMIT, xpath)
            if result and result.startswith('OK:'):
                self.log(f"   ✅ SAP Form Submit — runtime id: {result[3:]}")
            else:
                self.log(f"   ⚠️ SAP Form Submit: {result}")
        except Exception as e:
            self.log(f"   ⚠️ SAP Form Submit error: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # ELEMENT FINDER — platform-aware
    # ══════════════════════════════════════════════════════════════════════════
    def _find_element(self, xpath, timeout=20):
        if self.platform == "Salesforce":
            return self._find_element_salesforce(xpath, timeout)
        return self._find_element_sap(xpath, timeout)

    def _find_element_sap(self, xpath, timeout=20):
        """
        SAP element finder.
        Now works because CORS flags allow JS to freely access all inner frames.
        Runs from inside CRMApplicationFrame for correct domain context.
        """
        deadline   = time.time() + timeout
        frame_path = None

        while time.time() < deadline:
            if not self.is_running:
                return None
            try:
                self.driver.switch_to.default_content()
                try:
                    self.driver.switch_to.frame("CRMApplicationFrame")
                except Exception:
                    time.sleep(0.5)
                    continue

                frame_path = self.driver.execute_script(_JS_FIND_FRAME_INDEX, xpath)
                if frame_path is not None:
                    self.log(f"   🔍 Found — frame path: {frame_path}")
                    break
            except Exception:
                pass
            time.sleep(0.3)

        if frame_path is None:
            self.log(f"   ❌ Element not found after {timeout}s")
            return None

        try:
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame("CRMApplicationFrame")
            for idx in frame_path:
                self.driver.switch_to.frame(idx)
            return WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        except Exception as e:
            self.log(f"   ⚠️ Frame navigation failed: {e}")
            return None

    def _find_element_salesforce(self, xpath, timeout=20):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.is_running:
                return None
            try:
                self.driver.switch_to.default_content()
                try:
                    el = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    self.log(f"   📍 Found in top frame (Salesforce)")
                    return el
                except:
                    pass
                frame_path = self.driver.execute_script(_JS_FIND_FRAME_INDEX, xpath)
                if frame_path is not None:
                    self.log(f"   📍 Found iframe {frame_path} (Salesforce)")
                    for idx in frame_path:
                        self.driver.switch_to.frame(idx)
                    return WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
            except Exception:
                pass
            time.sleep(0.3)
        self.log(f"   ❌ Not found after {timeout}s (Salesforce)")
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE READY WAIT
    # ══════════════════════════════════════════════════════════════════════════
    def _wait_for_page_ready(self, timeout=30):
        if self.platform == "Salesforce":
            self._wait_salesforce(timeout)
        else:
            self._wait_sap(timeout)

    def _wait_sap(self, timeout=30):
        if not self.is_running:
            return
        self.driver.switch_to.default_content()
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script(
                    "return !!document.getElementById('CRMApplicationFrame');"
                )
            )
        except:
            return
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.is_running:
                return
            try:
                ready = self.driver.execute_script("""
                    try {
                        var f = document.getElementById('CRMApplicationFrame');
                        if (!f || !f.contentWindow) return false;
                        return f.contentWindow.frames.length > 0;
                    } catch(e) { return false; }
                """)
                if ready:
                    return
            except:
                pass
            time.sleep(0.3)

    def _wait_salesforce(self, timeout=30):
        if not self.is_running:
            return
        self.driver.switch_to.default_content()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.is_running:
                return
            try:
                ready = self.driver.execute_script("""
                    if (document.readyState !== 'complete') return false;
                    var spinners = document.querySelectorAll(
                        '.slds-spinner,lightning-spinner,.forcePageSpinner,' +
                        '[class*="loading"],[class*="spinner"]'
                    );
                    for (var i = 0; i < spinners.length; i++) {
                        var s = window.getComputedStyle(spinners[i]);
                        if (s.display !== 'none' && s.visibility !== 'hidden') return false;
                    }
                    return true;
                """)
                if ready:
                    return
            except:
                pass
            time.sleep(0.3)

    # ══════════════════════════════════════════════════════════════════════════
    # XPATH BUILDER
    # ══════════════════════════════════════════════════════════════════════════
    def _build_xpath(self, target, row, action, step):
        if action == "Smart Click (Column)":
            val = get_safe_xpath_string(str(row[step['column']]).strip())
            return f"//a[contains(normalize-space(.), {val})]"

        if target.startswith(("/", "(")):
            return target

        # Plain word with no spaces — could be an ID but we wrap it safely
        if " " not in target and "/" not in target and "&" not in target:
            # Try @title first (stable), fall back to @id (may be dynamic on SAP)
            safe = get_safe_xpath_string(target)
            return f"//*[@title={safe}] | //*[@id={safe}]"

        safe = get_safe_xpath_string(target)
        return (
            f"//*[@title={safe}]"
            f" | //a[normalize-space(.)={safe}]"
            f" | //button[normalize-space(.)={safe}]"
            f" | //span[normalize-space(.)={safe}]"
            f" | //div[normalize-space(.)={safe}]"
            f" | //td[normalize-space(.)={safe}]"
            f" | //li[normalize-space(.)={safe}]"
            f" | //input[@value={safe}]"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTION DISPATCHER
    # ══════════════════════════════════════════════════════════════════════════
    def _dispatch_action(self, action, el, step, row):
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',inline:'nearest'});", el
            )
            time.sleep(0.05)

            if action in ("Click Element", "Smart Click", "Smart Click (Column)",
                          "Click Button", "Click Link", "Click Sidebar"):
                # From the working code: simple JS click works fine when
                # CORS isolation is disabled — no need for 5-strategy fallback
                try:
                    self.driver.execute_script("arguments[0].click();", el)
                except:
                    el.click()

            elif action == "Double Click Element":
                self.driver.execute_script(
                    "var e=new MouseEvent('dblclick',{bubbles:true});"
                    "arguments[0].dispatchEvent(e);", el
                )

            elif action == "Clear Field":
                self._safe_click(el)
                el.send_keys(Keys.CONTROL + "a")
                el.send_keys(Keys.DELETE)

            elif action == "Backspace (Key)":
                self._safe_click(el)
                el.send_keys(Keys.BACK_SPACE)

            elif action == "Type (Standard)":
                val = str(row[step['column']]).strip()
                # From working code: handle float-to-int for numeric Excel cells
                self._clear_and_type(el, val)

            elif action == "Type & Tab":
                self._clear_and_type(el, str(row[step['column']]).strip())
                el.send_keys(Keys.TAB)

            elif action == "Type & Select":
                val = str(row[step['column']]).strip()
                if el.tag_name.lower() == "select":
                    sel_obj = Select(el)
                    try:
                        sel_obj.select_by_visible_text(val)
                    except:
                        for opt in sel_obj.options:
                            if val.lower() in opt.text.lower():
                                sel_obj.select_by_visible_text(opt.text)
                                break
                    self.driver.execute_script(
                        "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", el
                    )
                else:
                    self._safe_click(el)
                    time.sleep(0.5)
                    safe_val    = get_safe_xpath_string(val)
                    popup_xpath = (
                        f"//li[normalize-space(.)={safe_val}]"
                        f" | //div[contains(@class,'lsPopup')]//span[normalize-space(.)={safe_val}]"
                        f" | //div[contains(@class,'sapMSelectList')]//li[normalize-space(.)={safe_val}]"
                        f" | //td[normalize-space(.)={safe_val}]"
                        f" | //a[normalize-space(.)={safe_val}]"
                    )
                    try:
                        opt_el = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, popup_xpath))
                        )
                        self.driver.execute_script("arguments[0].click();", opt_el)
                    except:
                        self._clear_and_type(el, val)
                        el.send_keys(Keys.ENTER)

            elif action == "Press Enter":
                el.send_keys(Keys.ENTER)

            elif action == "Press Tab":
                el.send_keys(Keys.TAB)

            else:
                self.log(f"⚠️ Unknown action '{action}' — skipped.")

        except Exception as e:
            raise Exception(f"Action '{action}' failed: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _safe_click(self, el):
        """Fallback click chain for non-SAP elements."""
        try:
            ActionChains(self.driver).move_to_element(el).pause(0.05).click().perform()
        except:
            try:
                el.click()
            except:
                self.driver.execute_script("arguments[0].click();", el)

    def _clear_and_type(self, el, value):
        # From working code: handle float Excel values cleanly
        try:
            f = float(value)
            if f == int(f):
                value = str(int(f))
        except (ValueError, TypeError):
            pass
        self._safe_click(el)
        time.sleep(0.05)
        el.send_keys(Keys.CONTROL + "a")
        el.send_keys(Keys.DELETE)
        el.send_keys(value)

    def stop_execution(self):
        self.is_running = False