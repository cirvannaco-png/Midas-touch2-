#!/usr/bin/env python3
"""Sync secret env vars to a Render service and (optionally) redeploy.

Why this exists
------------
`render.yaml` declares BOT_TOKEN / CHAT_ID / ADMIN_CHAT_ID / SECRET_KEY /
WEBHOOK_SECRET_TOKEN
with `sync: false`, which means Render never manages their values - somebody
has to paste them into the dashboard by hand. That is exactly how the service
ended up booting with a WEBHOOK_SECRET_TOKEN that Telegram rejected.

This script makes that step reproducible:

  * values come from the environment (GitLab CI/CD variables in automation),
  * WEBHOOK_SECRET_TOKEN is generated when absent and always validated
    against Telegram's ``^[A-Za-z0-9_-]{1,256}$`` before it is uploaded,
  * env vars are PUT to the Render API, then a deploy is triggered so the
    new values are actually picked up.

Usage:
    RENDER_API_KEY=rnd_xxx RENDER_SERVICE_ID=srv-xxx \
        python scripts/render_sync_secrets.py [--dry-run] [--no-deploy]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request

RENDER_API = "https://api.render.com/v1"

# Same constraint enforced by app.config.Settings._validate_webhook_secret_token.
TELEGRAM_SECRET_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{1,256}")

# Secrets render.yaml marks `sync: false`. Optional ones are skipped when unset.
REQUIRED_SECRETS = ("BOT_TOKEN", "CHAT_ID", "ADMIN_CHAT_ID", "SECRET_KEY")
GENERATED_SECRETS = ("WEBHOOK_SECRET_TOKEN",)


class RenderSyncError(RuntimeError):
    """Raised for any unresoverable configuration or API failure."""


def generate_webhook_secret_token() -> str:
    """Return a token that always satisfies Telegram's charset rule.

    ``token_hex`` is used rather than ``token_urlsafe``/base64 because the
    latter emit '+', '/' and '=' which Telegram's setWebhook rejects.
    """
    return secrets.token_hex(32)


def validate_webhook_secret_token(value: str) -> str:
    if not TELEGRAM_SECRET_TOKEN_RE.fullmatch(value):
        raise RenderSyncError(
            "WEBHOOK_QPÔ‘UÕÒÑSˆ]\ÝX]Ú–ÐKV˜K^ŒNWËW^ÌKMŸI‚ˆŠ[YÜ˜[IÜÈ™\]Z\™[Y[›ÜˆÙXÜ™]ÝÚÙ[ŠKˆ‚ˆ”™YÙ[™\˜]HÚ]ˆÜ[œÜÛ˜[™Z^Ìˆ‚ˆ
Bˆ™]\›ˆ˜[YB‚‚™YˆÛÛXÝÜÙXÜ™]Ê[ŽˆXÝÜÝ‹Ý—JHOˆXÝÜÝ‹Ý—N‚ˆˆˆZ[H[‹]˜\ˆ^[ØYœ›ÛHH›ØÙ\ÜÈ[š\›Û›Y[ˆˆˆ‚ˆZ\ÜÚ[™ÈHÚÈ›ÜˆÈ[ˆ‘TURT‘QÔÑPÔ‘UÈYˆ›Ý[‹™Ù]
ÊWBˆYˆZ\ÜÚ[™Î‚ˆ˜Z\ÙH™[™\”Þ[˜Ñ\œ›ÜŠˆ“Z\ÜÚ[™È™\]Z\™YÙXÜ™]
ÊNˆ‚ˆ
È‹‹š›Ú[ŠZ\ÜÚ[™ÊBˆ
È‹ˆY[H\È›ÝXÝYÛX\ÚÙYÚ]X˜Ð’KÐÑˆ˜\šXX›\Ëˆ‚ˆ
B‚ˆ^[ØYHÜNˆ[–Ú×H›ÜˆH[ˆ‘TURT‘QÔÑPÔ‘UßB‚ˆ›ÜˆÙ^H[ˆÑS‘TUQÔÑPÔ‘UÎ‚ˆ˜[YHH[‹™Ù]
Ù^JHÜˆÙ[™\˜]WÝÙXšÛÚ×ÜÙXÜ™]ÝÚÙ[Š
Bˆ^[ØYÚÙ^WHH˜[Y]WÝÙXšÛÚ×ÜÙXÜ™]ÝÚÙ[Š˜[YJB‚ˆ™]\›ˆ^[ØY‚‚™YˆÜ™\]Y\Ý
Y]ÙˆÝ‹]ˆÝ‹\WÚÙ^NˆÝ‹›ÙNˆØš™XÝ›Û™HH›Û™JHOˆØš™XÝ‚ˆ]HHœÛÛ‹™[\Ê›ÙJK™[˜ÛÙJ
HYˆ›ÙH\È›Ý›Û™H[ÙH›Û™Bˆ™\HH\›X‹™\]Y\Ý”™\]Y\Ý
ˆˆžÔ‘S‘T—ÐT_^Ü]H‹ˆ]OY]KˆY]Ù[Y]ÙˆXY\œÏ^Âˆ]]Üš^˜][ÛˆŽˆˆ™X\™\ˆØ\WÚÙ^_H‹ˆXØÙ\Žˆ˜\XØ][Û‹ÚœÛÛˆ‹ˆÛÛ[U\HŽˆ˜\XØ][Û‹ÚœÛÛˆ‹ˆKˆ
BˆžN‚ˆÚ]\›X‹œ™\]Y\Ý\›Ü[Š™\K[Y[Ý]LÌ
H\È™\Ü‚ˆ˜]ÈH™\Üœ™XY

K™XÛÙJ
HÜˆ›[‚ˆ^Ù\\›X‹™\œ›Ü‹’\œ›Üˆ\È^Î‚ˆ]Z[H^Ëœ™XY

K™XÛÙJ\œ›ÜœÏHœ™\XÙHŠBˆ˜Z\ÙH™[™\”Þ[˜Ñ\œ›ÜŠˆ”™[™\ˆTHÛY]ÙHÜ]H˜Z[YÞÙ^Ë˜ÛÙ_WNˆÙ]Z[HŠHœ›ÛH^Âˆ^Ù\\›X‹™\œ›Ü‹•T“\œ›Üˆ\È^Î‚ˆ˜Z\ÙH™[™\”Þ[˜Ñ\œ›ÜŠˆ”™[™\ˆTHÛY]ÙHÜ]H[œ™XXÚX›NˆÙ^Ëœ™X\ÛÛŸHŠHœ›ÛH^Âˆ™]\›ˆœÛÛ‹›ØYÊ˜]ÊB‚‚™Yˆ]Ù[—Ý˜\œÊÙ\šXÙWÚYˆÝ‹\WÚÙ^NˆÝ‹XY[Y\ÎˆXÝÜÝ‹Ý—JHOˆ›Û™N‚ˆˆˆ”™\XÙHHÙ\šXÙIÜÈÙXÜ™][ˆ˜\œË‚‚ˆ™[™\‰ÜÈUÜÙ\šXÙ\ËÞÚYKÙ[‹]˜\œÈ™\XÙ\ÈHÚÛH\ÝÛÈBˆ›Û‹\ÙXÜ™]˜\œÈXÛ\™Y[ˆ™[™\‹žX[[\™H™K\Ù[[˜Ú[™ÙYžH™XY[™ÂˆHÝ\œ™[\Ýš\œÝ[™Y\™Ú[™Ë‚ˆˆˆ‚ˆÝ\œ™[HÜ™\]Y\Ý
‘ÑU‹ˆ‹ÜÙ\šXÙ\ËÞÜÙ\šXÙWÚYKÙ[‹]˜\œÈ‹\WÚÙ^JBˆ^\Ý[™ÎˆXÝÜÝ‹Ý—HHßBˆYˆ\Ú[œÝ[˜ÙJÝ\œ™[\Ý
N‚ˆ›Üˆ][H[ˆÝ\œ™[‚ˆ]ˆH][K™Ù]
™[•˜\ˆ‹][JHYˆ\Ú[œÝ[˜ÙJ][KXÝ
H[ÙHßBˆÙ^HH]‹™Ù]
šÙ^H‚ˆYˆÙ^H[™˜[YHˆ[ˆ]Ž‚ˆ^\Ý[™ÖÚÙ^WHH]–È˜[YH—B‚ˆY\™ÙYHÊŠ™^\Ý[™Ë
Š˜[Y\ßBˆÜ™\]Y\Ý
ˆ”U‹ˆˆ‹ÜÙ\šXÙ\ËÞÜÙ\šXÙWÚYKÙ[‹]˜\œÈ‹ˆ\WÚÙ^KˆÞÈšÙ^HŽˆË˜[YHŽˆŸH›ÜˆËˆ[ˆÛÜY
Y\™ÙYš][\Ê
JWKˆ
B‚‚™YˆšYÙÙ\—Ù\ÞJÙ\šXÙWÚYˆÝ‹\WÚÙ^NˆÝŠHOˆÝŽ‚ˆ™\Ý[HÜ™\]Y\Ý
”ÔÕ‹ˆ‹ÜÙ\šXÙ\ËÞÜÙ\šXÙWÚYKÙ\Þ\È‹\WÚÙ^KÈ˜ÛX\ØXÚHŽˆ™×Û›ÝØÛX\ˆŸJBˆYˆ\Ú[œÝ[˜ÙJ™\Ý[XÝ
N‚ˆ™]\›ˆÝŠ™\Ý[™Ù]
šY‹[šÛ›ÝÛˆŠJBˆ™]\›ˆ[šÛ›ÝÛˆ‚‚‚™YˆXZ[Š\™ÝŽˆ\ÝÜÝ—H›Û™HH›Û™JHOˆ[‚ˆ\œÙ\ˆH\™Ü\œÙK\™Ý[Y[\œÙ\Š\ØÜš\[ÛW×ÙØ××ÊBˆ\œÙ\‹˜YØ\™Ý[Y[
‹KYžK\[ˆ‹XÝ[ÛHœÝÜ™WÝYH‹[H˜[Y]HÛ›KØ[›ÈT\ÈŠBˆ\œÙ\‹˜YØ\™Ý[Y[
‹K[›ËY\ÞH‹XÝ[ÛHœÝÜ™WÝYH‹[H\]H[ˆ˜\œÈ]ÚÚ\™Y\ÞHŠBˆ\™ÜÈH\œÙ\‹œ\œÙWØ\™ÜÊ\™ÝŠB‚ˆ[ˆHXÝ
ÜË™[š\›Û›Y[
BˆžN‚ˆ˜[Y\ÈHÛÛXÝÜÙXÜ™]Ê[ŠBˆ^Ù\™[™\”Þ[˜Ñ\œ›Üˆ\È^Î‚ˆš[
ˆ™\œ›ÜŽˆÙ^ßH‹š[O\Þ\ËœÝ\œŠBˆ™]\›ˆB‚ˆÈ™]™\ˆš[˜[Y\ÈHÛ›HÙ^H˜[Y\Ë‚ˆš[
œÙXÜ™]È™\\™Yˆ‹‹‹š›Ú[ŠÛÜY
˜[Y\ÊJJBˆYˆ\™ÜË™žWÜ[Ž‚ˆš[
™žH[Žˆ›È™[™\ˆTHØ[ÈXYHŠBˆ™]\›ˆ‚ˆ\WÚÙ^HH[‹™Ù]
”‘S‘T—ÐTWÒÑVHŠBˆÙ\šXÙWÚYH[‹™Ù]
”‘S‘T—ÔÑT•’PÑWÒQŠBˆYˆ›Ý\WÚÙ^HÜˆ›ÝÙ\šXÙWÚY‚ˆš[
™\œ›ÜŽˆ‘S‘T—ÐTWÒÑVH[™‘S‘T—ÔÑT•’PÑWÒQ]\Ý™HÙ]‹š[O\Þ\ËœÝ\œŠBˆ™]\›ˆB‚ˆžN‚ˆ]Ù[—Ý˜\œÊÙ\šXÙWÚY\WÚÙ^K˜[Y\ÊBˆš[
ˆ™[ˆ˜\œÈÞ[˜ÙYÈÜÙ\šXÙWÚYHŠBˆYˆ›Ý\™ÜË››×Ù\ÞN‚ˆš[
ˆ™\ÞHšYÙÙ\™YˆÝšYÙÙ\—Ù\ÞJÙ\šXÙWÚY\WÚÙ^J_HŠBˆ^Ù\™[™\”Þ[˜Ñ\œ›Üˆ\È^Î‚ˆš[
ˆ™\œ›ÜŽˆÙ^ßH‹š[O\Þ\ËœÝ\œŠBˆ™]\›ˆBˆ™]\›ˆ‚‚šYˆ×Û˜[YW×ÈOH—×ÛXZ[—×ÈŽ‚ˆ˜Z\ÙHÞ\Ý[Q^]
XZ[Š
JB