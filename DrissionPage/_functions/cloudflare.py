# -*- coding:utf-8 -*-
"""
Cloudflare Turnstile challenge helper utilities adapted from the botasaurus project.
"""
from __future__ import annotations

from enum import Enum
from random import randint, uniform
from time import sleep, time
from typing import TYPE_CHECKING, Optional, Tuple, Union

from ..errors import ElementNotFoundError

if TYPE_CHECKING:  # pragma: no cover
    from .._elements.chromium_element import ChromiumElement, ShadowRoot
    from .._pages.chromium_base import ChromiumBase


class Opponent(Enum):
    CLOUDFLARE = 'cloudflare'


class CloudflareDetectionException(RuntimeError):
    """Raised when Cloudflare keeps flagging the automation."""


class ShadowRootClosedException(RuntimeError):
    """Raised when the widget shadow-root detaches while interacting with it."""


def click_restoring_human_behaviour(driver: ChromiumBase, checkbox: ChromiumElement) -> None:
    """Move the cursor with slight jitter before clicking the element."""
    if not checkbox:
        return
    offset_x = randint(-3, 3)
    offset_y = randint(-3, 3)
    driver.actions.move_to(checkbox, offset_x=offset_x, offset_y=offset_y,
                           duration=uniform(0.25, 0.45))
    sleep(uniform(0.05, 0.15))
    driver.actions.click()


def click_point_restoring_human_behaviour(driver: ChromiumBase, x: float, y: float) -> None:
    driver.actions.move_to((x, y), duration=uniform(0.3, 0.55))
    sleep(uniform(0.05, 0.12))
    driver.actions.click()


def wait_till_document_is_ready(tab: ChromiumBase, wait_for_complete_page_load: bool,
                                timeout: float = 60) -> None:
    desired_states = ('interactive', 'complete') if not wait_for_complete_page_load else ('complete',)
    end_time = time() + timeout
    while time() < end_time:
        sleep(0.1)
        try:
            ready_state = tab._js_ready_state  # pylint: disable=protected-access
        except Exception:  # noqa: BLE001
            continue
        if ready_state in desired_states:
            return
    raise TimeoutError('Document did not become ready within %.0f seconds' % timeout)


def is_taking_long(shadow_root: ShadowRoot) -> bool:
    try:
        text = shadow_root.run_js('return (this.innerText || this.textContent || "").toLowerCase();')
    except Exception:  # noqa: BLE001
        return False
    return 'taking longer than expected' in (text or '')


def get_rayid(driver: ChromiumBase) -> Optional[str]:
    el = _safe_ele(driver, 'css:.ray-id code', timeout=0)
    return el.text.strip() if el else None


def get_turnstile_parent(driver: ChromiumBase) -> Optional[ChromiumElement]:
    locator = ('css selector',
               '[name="cf-turnstile-response"]:not(#cf-invisible-turnstile [name="cf-turnstile-response"])')
    turnstile = _safe_ele(driver, locator, timeout=0)
    if turnstile:
        parent = turnstile.parent()
        return parent if parent else None
    return None


def get_iframe_tab(driver: ChromiumBase) -> Optional[ShadowRoot]:
    shadow_root_element = get_turnstile_parent(driver)
    if not shadow_root_element:
        return None
    shadow_root = shadow_root_element.shadow_root
    if shadow_root is None:
        raise ShadowRootClosedException
    return shadow_root


def get_iframe_content(driver: ChromiumBase) -> Optional[Union[ShadowRoot, ChromiumElement]]:
    iframe_tab = get_iframe_tab(driver)
    if not iframe_tab:
        return None
    nested = _first_child_shadow(iframe_tab)
    return nested or iframe_tab


def get_widget_iframe_via_get_iframe_by_link(driver: ChromiumBase):
    try:
        return driver.get_frame('xpath://iframe[contains(@src,"challenges.cloudflare.com")]')
    except Exception:  # noqa: BLE001
        return None


def get_widget_iframe(driver: ChromiumBase) -> Optional[Union[ShadowRoot, ChromiumElement]]:
    try:
        return get_iframe_content(driver)
    except ShadowRootClosedException:
        return get_widget_iframe_via_get_iframe_by_link(driver)
    except Exception:  # noqa: BLE001
        return None


def wait_till_cloudflare_leaves(driver: ChromiumBase, previous_ray_id: Optional[str]) -> None:
    start_time = time()
    wait_time = 30
    while True:
        if not driver.is_bot_detected_by_cloudflare():
            return
        current_ray = get_rayid(driver)
        if previous_ray_id and current_ray and current_ray != previous_ray_id:
            wait_time = 12
            start_time = time()
            while True:
                if not driver.is_bot_detected_by_cloudflare():
                    return
                iframe = get_iframe_content(driver)
                if iframe:
                    checkbox = get_checkbox(iframe)
                    if checkbox or is_taking_long(iframe):
                        raise CloudflareDetectionException('Cloudflare has detected us.')
                if time() - start_time > wait_time:
                    raise CloudflareDetectionException('Cloudflare has not given us a captcha.')
                sleep(1)
        if time() - start_time > wait_time:
            raise CloudflareDetectionException(
                'Cloudflare is taking too long to verify Captcha submission.'
            )
        sleep(1)


def solve_full_cf(driver: ChromiumBase) -> None:
    iframe = _wait_for_iframe(driver)
    if iframe is None:
        return
    previous_ray_id = get_rayid(driver)
    start_time = time()
    wait_time = 16
    while True:
        iframe = _wait_for_iframe(driver)
        checkbox = get_checkbox(iframe)
        if checkbox:
            click_restoring_human_behaviour(driver, checkbox)
            wait_till_cloudflare_leaves(driver, previous_ray_id)
            wait_till_document_is_ready(driver, driver._load_mode != 'eager')  # pylint: disable=protected-access
            return
        if time() - start_time > wait_time:
            raise CloudflareDetectionException('Cloudflare has not given us a captcha.')
        sleep(1)


def get_checkbox(iframe: Union[ShadowRoot, ChromiumElement, 'ChromiumBase']):
    if hasattr(iframe, 'ele'):
        checkbox = _safe_ele(iframe, 'css:input[type="checkbox"]', timeout=0)
        if checkbox:
            return checkbox
        button = _safe_ele(iframe, 'css:[role="button"]', timeout=0)
        if button:
            return button
    owner = getattr(iframe, 'owner', iframe)
    try:
        return get_turnstile_parent(owner)
    except Exception:  # noqa: BLE001
        return None


def wait_for_widget_iframe(driver: ChromiumBase):
    iframe = get_widget_iframe(driver)
    while not iframe:
        if not driver.is_bot_detected_by_cloudflare():
            return 'bot_not_detected'
        sleep(0.75)
        iframe = get_widget_iframe(driver)
    return iframe


def wait_till_cloudflare_leaves_widget(driver: ChromiumBase) -> None:
    wait_time = 30
    start_time = time()
    while True:
        iframe = get_widget_iframe(driver)
        if iframe:
            if issuccess(iframe):
                return
            if isfailure(iframe) or is_taking_long(iframe):
                raise CloudflareDetectionException('Cloudflare has detected us.')
        if not driver.is_bot_detected_by_cloudflare():
            return
        if time() - start_time > wait_time:
            raise CloudflareDetectionException('Cloudflare has detected us.')
        sleep(1)


def issuccess(iframe: Union[ShadowRoot, ChromiumElement]) -> bool:
    success = _safe_ele(iframe, 'css:#success[style*="display: grid"][style*="visibility: visible"]', timeout=0)
    return bool(success)


def isfailure(iframe: Union[ShadowRoot, ChromiumElement]) -> bool:
    failure = _safe_ele(iframe, 'css:#fail[style*="display: grid"][style*="visibility: visible"]', timeout=0)
    return bool(failure)


def perform_click(driver: ChromiumBase, el: ChromiumElement) -> None:
    if not el:
        return
    location = el.rect.location
    size = el.rect.size
    x_center = location[0] + size[0] / 2
    y_center = location[1] + size[1] / 2
    x = x_center + randint(-5, 5)
    y = y_center + randint(-5, 5)
    click_point_restoring_human_behaviour(driver, x, y)


def click_clf_checkbox_widget(driver: ChromiumBase):
    turnstile_parent = get_turnstile_parent(driver)
    if turnstile_parent:
        perform_click(driver, turnstile_parent)


def solve_widget_cf(driver: ChromiumBase) -> None:
    try:
        iframe = wait_for_widget_iframe(driver)
        if iframe == 'bot_not_detected':
            wait_till_document_is_ready(driver, driver._load_mode != 'eager')  # pylint: disable=protected-access
            return
    except ShadowRootClosedException:
        sleep(0.75)
        click_clf_checkbox_widget(driver)
        return
    wait_time = 16
    start_time = time()
    while True:
        iframe = wait_for_widget_iframe(driver)
        if iframe == 'bot_not_detected':
            wait_till_document_is_ready(driver, driver._load_mode != 'eager')  # pylint: disable=protected-access
            return
        if issuccess(iframe):
            wait_till_document_is_ready(driver, driver._load_mode != 'eager')  # pylint: disable=protected-access
            return
        checkbox = get_checkbox(iframe)
        if checkbox:
            click_restoring_human_behaviour(driver, checkbox)
            wait_till_cloudflare_leaves_widget(driver)
            wait_till_document_is_ready(driver, driver._load_mode != 'eager')  # pylint: disable=protected-access
            return
        if time() - start_time > wait_time:
            raise CloudflareDetectionException('Cloudflare has not given us a captcha.')
        sleep(1)


def bypass_if_detected(driver: ChromiumBase) -> bool:
    opponent = get_bot_detected_by(driver)
    if opponent != Opponent.CLOUDFLARE:
        return False
    if (driver.title or '').strip() == 'Just a moment...':
        solve_full_cf(driver)
    else:
        solve_widget_cf(driver)
    return True


def is_bot_detected_by_cloudflare(driver: ChromiumBase) -> bool:
    if driver is None:
        return False
    title = ''
    url = ''
    try:
        title = (driver.title or '').lower()
        url = (driver.url or '').lower()
    except Exception:  # noqa: BLE001
        pass
    if 'cloudflare' in title or 'just a moment' in title or 'checking your browser' in title:
        return True
    if 'cdn-cgi/challenge-platform' in url or 'challenges.cloudflare.com' in url:
        return True
    return bool(get_turnstile_parent(driver))


def get_bot_detected_by(driver: ChromiumBase) -> Optional[Opponent]:
    return Opponent.CLOUDFLARE if is_bot_detected_by_cloudflare(driver) else None


def _safe_ele(owner, locator, timeout=0.5):
    if not owner:
        return None
    try:
        ele = owner.ele(locator, timeout=timeout)
    except ElementNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        return None
    return ele if ele else None


def _first_child_shadow(shadow_root: ShadowRoot) -> Optional[ShadowRoot]:
    if not shadow_root:
        return None
    try:
        children = shadow_root.children('*', timeout=0)
    except ElementNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        return None
    if not children:
        return None
    for child in children:
        try:
            nested = child.shadow_root
        except Exception:  # noqa: BLE001
            nested = None
        if nested:
            return nested
    return None


def _wait_for_iframe(driver: ChromiumBase):
    iframe = get_iframe_content(driver)
    while not iframe:
        if not driver.is_bot_detected_by_cloudflare():
            wait_till_document_is_ready(driver, driver._load_mode != 'eager')  # pylint: disable=protected-access
            return None
        sleep(0.75)
        iframe = get_iframe_content(driver)
    return iframe

