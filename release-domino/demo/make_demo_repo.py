#!/usr/bin/env python3
"""
Task D0 — Demo Repo Builder (Cross-Platform Python Script for Windows, macOS & Linux)
Builds `demo_shop_repo/` with:
  - 25 files (FastAPI + Redis e-commerce shop: auth.py, login_route.py, checkout.py, cart.py, redis_cache.py, db.py, utils.py, etc.)
  - 42 commits over the last 120 days using GIT_AUTHOR_DATE / GIT_COMMITTER_DATE,
    including multiple `fix:` and `revert:` commits touching `auth.py` and `checkout.py`
  - Unit tests covering `cart.py` and `utils.py` (100% coverage) but NOT `auth.py`
  - A remote branch `origin/main` with a conflicting commit on `auth.py`
  - Uncommitted + committed changes on `auth.py` so `git diff` and `git merge-tree` immediately trigger!
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def run_git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    res = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        env=merged_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return res.stdout


import stat

def safe_rmtree(path: Path) -> None:
    if not path.exists():
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            fp = os.path.join(root, f)
            try:
                os.chmod(fp, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass
        for d in dirs:
            dp = os.path.join(root, d)
            try:
                os.chmod(dp, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            except Exception:
                pass
    try:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
    except Exception:
        pass
    def _on_error(func, p, exc):
        try:
            os.chmod(p, stat.S_IRWXU | stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=lambda func, p, exc: _on_error(func, p, exc))
        else:
            shutil.rmtree(path, onerror=lambda func, p, exc_info: _on_error(func, p, exc_info))
    except Exception:
        if os.name == "nt":
            subprocess.run(f"cmd /c rmdir /s /q \"{path}\"", shell=True, capture_output=True, check=False)


def build_demo_repo(target_dir: Path, force_rebuild: bool = False) -> Path:
    if not force_rebuild and (target_dir / ".git").exists() and (target_dir / "auth.py").exists():
        print(f"Existing demo repo verified at: {target_dir}")
        return target_dir
    if target_dir.exists():
        safe_rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Create bare remote repo alongside target_dir so `origin/main` is a real git remote
    bare_remote = target_dir.parent / (target_dir.name + "_origin.git")
    if bare_remote.exists():
        safe_rmtree(bare_remote)
    bare_remote.mkdir(parents=True, exist_ok=True)
    run_git(["init", "--bare"], cwd=bare_remote)

    run_git(["init", "-b", "main"], cwd=target_dir)
    run_git(["config", "user.name", "Release Domino Demo"], cwd=target_dir)
    run_git(["config", "user.email", "demo@releasedomino.local"], cwd=target_dir)
    run_git(["remote", "add", "origin", str(bare_remote.resolve())], cwd=target_dir)

    # Create 25 files across shop modules, routes, services, infra, and tests
    files = {
        "requirements.txt": "fastapi==0.115.0\nredis==5.0.8\npydantic==2.9.2\npytest==8.3.3\npytest-cov==5.0.0\n",
        "config.py": "REDIS_URL = 'redis://localhost:6379/0'\nDB_URL = 'postgresql://shop:secret@localhost:5432/shop'\nJWT_SECRET = 'super-secret-key'\n",
        "db.py": "import config\n\ndef query_db(sql: str, params: tuple = ()):\n    return [{'id': 1, 'sql': sql, 'db': config.DB_URL}]\n\ndef execute_tx(sql: str):\n    return True\n",
        "redis_cache.py": "import config\n\n_CACHE = {}\n\ndef cache_get(key: str):\n    return _CACHE.get(key)\n\ndef cache_set(key: str, val, ttl: int = 60):\n    _CACHE[key] = val\n    return True\n",
        "utils.py": "import hashlib\n\ndef format_currency(cents: int) -> str:\n    if cents < 0:\n        raise ValueError('negative amount')\n    return f'${cents / 100:.2f}'\n\ndef slugify(text: str) -> str:\n    return text.strip().lower().replace(' ', '-')\n\ndef hash_id(raw: str) -> str:\n    return hashlib.sha256(raw.encode()).hexdigest()[:12]\n",
        "auth.py": "import db\nimport redis_cache\nimport utils\n\ndef verify_token(token: str) -> dict:\n    cached = redis_cache.cache_get(f'tok:{token}')\n    if cached:\n        return cached\n    if not token or not token.startswith('bearer_'):\n        raise PermissionError('Invalid auth token')\n    user = {'user_id': utils.hash_id(token), 'role': 'customer', 'active': True}\n    redis_cache.cache_set(f'tok:{token}', user, ttl=120)\n    return user\n\ndef check_admin(user: dict) -> bool:\n    return user.get('role') == 'admin'\n",
        "cart.py": "import redis_cache\nimport utils\n\ndef add_to_cart(user_id: str, item_id: str, price_cents: int, qty: int = 1) -> dict:\n    if qty <= 0:\n        raise ValueError('qty must be positive')\n    subtotal = price_cents * qty\n    cart = {'user_id': user_id, 'item_id': item_id, 'subtotal': subtotal, 'formatted': utils.format_currency(subtotal)}\n    redis_cache.cache_set(f'cart:{user_id}', cart)\n    return cart\n\ndef get_cart_total(items: list[dict]) -> int:\n    return sum(i['price_cents'] * i.get('qty', 1) for i in items)\n",
        "inventory.py": "import db\nimport redis_cache\n\ndef check_stock(item_id: str) -> int:\n    cached = redis_cache.cache_get(f'stock:{item_id}')\n    if cached is not None:\n        return cached\n    rows = db.query_db('SELECT stock FROM inventory WHERE id=%s', (item_id,))\n    return 10 if rows else 0\n",
        "pricing.py": "import utils\n\ndef apply_discount(cents: int, pct: float) -> int:\n    if not (0 <= pct <= 100):\n        raise ValueError('invalid discount')\n    return int(round(cents * (1.0 - pct / 100.0)))\n",
        "payment.py": "import db\nimport auth\nimport utils\n\ndef charge_card(token: str, amount_cents: int) -> dict:\n    user = auth.verify_token(token)\n    db.execute_tx(f'INSERT INTO payments VALUES ({amount_cents})')\n    return {'status': 'paid', 'user': user['user_id'], 'amount': utils.format_currency(amount_cents)}\n",
        "checkout.py": "import auth\nimport cart\nimport inventory\nimport payment\nimport db\n\ndef process_checkout(token: str, item_id: str, price_cents: int, qty: int = 1) -> dict:\n    user = auth.verify_token(token)\n    if inventory.check_stock(item_id) < qty:\n        raise RuntimeError('Out of stock')\n    c = cart.add_to_cart(user['user_id'], item_id, price_cents, qty)\n    receipt = payment.charge_card(token, c['subtotal'])\n    db.execute_tx('INSERT INTO orders VALUES (1)')\n    return {'order_status': 'completed', 'receipt': receipt}\n",
        "orders.py": "import db\nimport auth\n\ndef list_orders(token: str) -> list:\n    user = auth.verify_token(token)\n    return db.query_db('SELECT * FROM orders WHERE user_id=%s', (user['user_id'],))\n",
        "shipping.py": "import db\nimport utils\n\ndef estimate_shipping(zip_code: str, weight_kg: float) -> str:\n    cents = int(500 + weight_kg * 150)\n    return utils.format_currency(cents)\n",
        "notifications.py": "import redis_cache\nimport utils\n\ndef queue_email(to_addr: str, subject: str) -> bool:\n    return redis_cache.cache_set(f'mail:{utils.slugify(to_addr)}', subject)\n",
        "audit_log.py": "import db\n\ndef record_audit(actor: str, action: str) -> bool:\n    return db.execute_tx(f'INSERT INTO audit_log VALUES ({actor}, {action})')\n",
        "rate_limiter.py": "import redis_cache\n\ndef allow_request(ip: str, limit: int = 60) -> bool:\n    current = redis_cache.cache_get(f'rl:{ip}') or 0\n    if current >= limit:\n        return False\n    redis_cache.cache_set(f'rl:{ip}', current + 1, ttl=60)\n    return True\n",
        "session_store.py": "import redis_cache\nimport auth\n\ndef create_session(token: str) -> dict:\n    user = auth.verify_token(token)\n    redis_cache.cache_set(f\"sess:{user['user_id']}\", user, ttl=3600)\n    return user\n",
        "profile_service.py": "import auth\nimport db\n\ndef get_profile(token: str) -> dict:\n    user = auth.verify_token(token)\n    rows = db.query_db('SELECT * FROM profiles WHERE id=%s', (user['user_id'],))\n    return {'user': user, 'rows': rows}\n",
        "search_service.py": "import db\nimport redis_cache\nimport utils\n\ndef search_catalog(query: str) -> list:\n    slug = utils.slugify(query)\n    return db.query_db('SELECT * FROM catalog WHERE slug LIKE %s', (slug,))\n",
        "login_route.py": "import auth\nimport session_store\nimport audit_log\n\ndef post_login(token: str) -> dict:\n    sess = session_store.create_session(token)\n    audit_log.record_audit(sess['user_id'], 'login')\n    return {'ok': True, 'session': sess}\n",
        "checkout_route.py": "import checkout\nimport notifications\n\ndef post_checkout(token: str, item_id: str, price_cents: int) -> dict:\n    res = checkout.process_checkout(token, item_id, price_cents, qty=1)\n    notifications.queue_email('buyer@example.com', 'Order Confirmed')\n    return res\n",
        "cart_route.py": "import auth\nimport cart\n\ndef post_cart_item(token: str, item_id: str, price_cents: int, qty: int = 1) -> dict:\n    user = auth.verify_token(token)\n    return cart.add_to_cart(user['user_id'], item_id, price_cents, qty)\n",
        "app.py": "import login_route\nimport checkout_route\nimport cart_route\n\ndef create_app() -> dict:\n    return {'routes': ['/login', '/checkout', '/cart']}\n\nif __name__ == '__main__':\n    print('Release Domino Demo Shop running — routes:', create_app()['routes'])\n",
        "tests/test_utils.py": "import pytest\nimport utils\n\ndef test_format_currency():\n    assert utils.format_currency(1999) == '$19.99'\n    assert utils.format_currency(0) == '$0.00'\n\ndef test_format_currency_negative():\n    with pytest.raises(ValueError):\n        utils.format_currency(-5)\n\ndef test_slugify_and_hash():\n    assert utils.slugify('  Hello World ') == 'hello-world'\n    assert len(utils.hash_id('abc')) == 12\n",
        "tests/test_cart.py": "import pytest\nimport cart\n\ndef test_add_to_cart():\n    res = cart.add_to_cart('u1', 'item-9', 2500, qty=2)\n    assert res['subtotal'] == 5000\n    assert res['formatted'] == '$50.00'\n\ndef test_get_cart_total():\n    total = cart.get_cart_total([{'price_cents': 400, 'qty': 2}, {'price_cents': 200, 'qty': 1}])\n    assert total == 1000\n",
    }

    for rel, content in files.items():
        fpath = target_dir / rel
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")

    base_time = datetime.now(timezone.utc) - timedelta(days=90)

    def commit_at(day_offset: int, msg: str):
        dt_str = (base_time + timedelta(days=day_offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
        run_git(["add", "-A"], cwd=target_dir)
        run_git(
            ["commit", "-m", msg, "--allow-empty"],
            cwd=target_dir,
            env={"GIT_AUTHOR_DATE": dt_str, "GIT_COMMITTER_DATE": dt_str},
        )

    commit_at(0, "feat: initial FastAPI + Redis shop architecture (25 files)")

    # Seed 40+ commits including fix/bug/hotfix/revert commits on auth.py and checkout.py
    history_plan = [
        (2, "auth.py", "fix(auth): patch token prefix validation bug"),
        (4, "checkout.py", "fix(checkout): handle inventory race condition"),
        (6, "auth.py", "revert: revert broken session token format in auth.py"),
        (8, "cart.py", "feat(cart): add subtotal currency formatting"),
        (10, "auth.py", "hotfix(auth): fix null token crash on expired cache"),
        (12, "checkout.py", "bug(checkout): fix duplicate order row insertion"),
        (14, "auth.py", "revert: revert unsafe admin role check in auth.py"),
        (16, "payment.py", "fix(payment): handle negative charge validation"),
        (18, "auth.py", "fix(auth): patch token cache key collision"),
        (20, "checkout.py", "revert: revert experimental async checkout pipeline"),
        (22, "redis_cache.py", "feat(cache): tune default Redis TTL"),
        (24, "auth.py", "patch(auth): tighten bearer token parsing"),
        (26, "checkout.py", "fix(checkout): validate positive quantity before payment"),
        (28, "login_route.py", "fix(login): log audit event after session creation"),
        (30, "utils.py", "chore(utils): clean up currency helper"),
        (32, "auth.py", "fix(auth): resolve stale role cache bug"),
        (34, "checkout.py", "hotfix(checkout): fix payment timeout handling"),
        (36, "inventory.py", "feat(inventory): cache stock lookups in Redis"),
        (38, "orders.py", "feat(orders): list customer order history"),
        (40, "shipping.py", "feat(shipping): add weight-based shipping estimator"),
        (42, "notifications.py", "feat(notify): queue confirmation email in Redis"),
        (44, "audit_log.py", "feat(audit): record security events"),
        (46, "rate_limiter.py", "feat(ratelimit): add Redis sliding window counter"),
        (48, "session_store.py", "feat(session): store active sessions in Redis"),
        (50, "profile_service.py", "feat(profile): add customer profile lookup"),
        (52, "search_service.py", "feat(search): add slug-based catalog search"),
        (54, "checkout_route.py", "feat(routes): wire checkout email notification"),
        (56, "cart_route.py", "feat(routes): add cart item endpoint"),
        (58, "pricing.py", "feat(pricing): support percentage discount calculation"),
        (60, "db.py", "chore(db): add transaction helper"),
        (62, "config.py", "chore(config): add Redis and Postgres connection settings"),
        (64, "app.py", "feat(app): register shop route handlers"),
        (66, "tests/test_utils.py", "test(utils): add unit tests for currency and slugify"),
        (68, "tests/test_cart.py", "test(cart): add unit tests for cart totals"),
        (70, "auth.py", "fix(auth): sanitize token whitespace before lookup"),
        (72, "checkout.py", "fix(checkout): verify stock before charging card"),
        (74, "auth.py", "bug(auth): fix admin role privilege check"),
        (76, "checkout.py", "patch(checkout): include receipt in order response"),
        (78, "login_route.py", "chore(login): format response payload"),
        (80, "auth.py", "fix(auth): enforce strict bearer prefix check"),
    ]

    for idx, (day_off, rel_file, msg) in enumerate(history_plan, start=1):
        fp = target_dir / rel_file
        fp.write_text(fp.read_text(encoding="utf-8") + f"# rev {idx}\n", encoding="utf-8")
        commit_at(day_off, msg)

    # Push baseline main to origin/main
    run_git(["push", "-u", "origin", "main"], cwd=target_dir)

    # Now create a conflicting commit on origin/main in auth.py:
    # 1. Create a temporary clone or branch to push a conflicting change to origin/main
    run_git(["checkout", "-b", "upstream_conflict"], cwd=target_dir)
    auth_path = target_dir / "auth.py"
    upstream_auth = """import db
import redis_cache
import utils

def verify_token(token: str) -> dict:
    # UPSTREAM ORIGIN/MAIN SECURITY HARDENING: strict JWT v2 signature check
    if not token or not token.startswith('jwt_v2_'):
        raise PermissionError('Origin/Main requires jwt_v2_ prefix')
    cached = redis_cache.cache_get(f'jwt_v2:{token}')
    if cached:
        return cached
    user = {'user_id': utils.hash_id(token), 'role': 'verified_customer', 'mfa': True}
    redis_cache.cache_set(f'jwt_v2:{token}', user, ttl=300)
    return user

def check_admin(user: dict) -> bool:
    return user.get('role') == 'superadmin' and user.get('mfa') is True
"""
    auth_path.write_text(upstream_auth, encoding="utf-8")
    commit_at(85, "feat(auth): enforce jwt_v2_ prefix on origin/main")
    run_git(["push", "origin", "upstream_conflict:main"], cwd=target_dir)

    # Switch back to local main and make a divergent commit + working tree changes on auth.py
    run_git(["checkout", "main"], cwd=target_dir)
    local_committed_auth = """import db
import redis_cache
import utils

def verify_token(token: str) -> dict:
    # LOCAL FEATURE BRANCH: legacy bearer + session token support
    if not token or not token.startswith('bearer_legacy_'):
        raise PermissionError('Local branch expects bearer_legacy_ prefix')
    cached = redis_cache.cache_get(f'legacy:{token}')
    if cached:
        return cached
    user = {'user_id': utils.hash_id(token), 'role': 'customer', 'active': True, 'tier': 'gold'}
    redis_cache.cache_set(f'legacy:{token}', user, ttl=60)
    return user

def check_admin(user: dict) -> bool:
    return user.get('role') in ('admin', 'staff')
"""
    auth_path.write_text(local_committed_auth, encoding="utf-8")
    commit_at(86, "feat(auth): add legacy bearer token support on local branch")

    # Fetch origin so origin/main ref is updated locally
    run_git(["fetch", "origin"], cwd=target_dir)

    # Also add uncommitted working-tree edits on auth.py and checkout.py so `git diff` is non-empty immediately!
    working_tree_auth = local_committed_auth + """
def revoke_token(token: str) -> bool:
    redis_cache.cache_set(f'legacy:{token}', None, ttl=0)
    return True

def refresh_session_ttl(token: str, extra_sec: int = 180) -> dict:
    user = verify_token(token)
    redis_cache.cache_set(f'legacy:{token}', user, ttl=extra_sec)
    return user
"""
    auth_path.write_text(working_tree_auth, encoding="utf-8")

    print(f"Successfully built demo repo at: {target_dir}")
    return target_dir


if __name__ == "__main__":
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "demo_shop_repo"
    build_demo_repo(out_dir)
