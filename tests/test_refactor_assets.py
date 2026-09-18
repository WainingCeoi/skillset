"""Regression checks for the FastAPI + React refactor skill templates."""

from __future__ import annotations

import asyncio
import importlib
import importlib.abc
import importlib.machinery
import json
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "refactor-to-fastapi-react"
MAIN = SKILL / "assets" / "backend" / "main.py"
API = SKILL / "assets" / "frontend" / "api.ts"
MAKEFILE = SKILL / "assets" / "Makefile"


class _HTTPException(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code


class _Headers:
    def __init__(self, scope: dict[str, object]):
        self._headers = dict(scope.get("headers", []))

    def get(self, name: str, default: str = "") -> str:
        return self._headers.get(name.encode(), default.encode()).decode()


class _StaticFiles:
    def __init__(self, *args: object, **kwargs: object):
        pass

    async def get_response(self, path: str, scope: dict[str, object]):
        if path in {"index.html", "assets/logo.svg"}:
            return path
        raise _HTTPException(404)


class _FastAPI:
    def __init__(self, **kwargs: object):
        self.state = types.SimpleNamespace()
        self.lifespan = kwargs["lifespan"]
        self.routes: list[tuple[str, object]] = []

    def add_middleware(self, *args: object, **kwargs: object) -> None:
        pass

    def mount(self, path: str, app: object, **kwargs: object) -> None:
        self.routes.append((path, app))

    def include_router(self, router: object, **kwargs: object) -> None:
        self.routes.append(("router", router))


@contextmanager
def _main_template(
    engine: object,
    build_engine: object,
    loaded: list[tuple[Path, bool]] | None = None,
    observed_imports: list[tuple[str, str | None]] | None = None,
    include_router_import: bool = False,
):
    """Execute main.py after replacing its intentional project placeholders."""
    source = MAIN.read_text().replace("from <engine> import <EngineClass>", "from engine import Engine")
    source = source.replace("<EngineClass>", "Engine").replace("<PROJECT>", "Test")
    if include_router_import:
        source = source.replace("# from .routers import ...", "from .routers import router")
        source = source.replace(
            '# app.include_router(<resource>.router, prefix="/api")   # repeat per resource',
            'app.include_router(router, prefix="/api")',
        )

    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = _FastAPI
    fastapi.Request = object
    cors = types.ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = object
    static = types.ModuleType("fastapi.staticfiles")
    static.StaticFiles = _StaticFiles
    engine_module = types.ModuleType("engine")
    engine_module.Engine = type(engine)
    package = types.ModuleType("app_api")
    package.__path__ = []
    deps = types.ModuleType("app_api.deps")
    deps.build_engine = build_engine
    dotenv = types.ModuleType("dotenv")

    def load_dotenv(path: Path, *, override: bool = False) -> None:
        if loaded is not None:
            loaded.append((Path(path), override))
        if override:
            os.environ["REFRACTOR_TEMPLATE_ENV"] = "from-dotenv"
        else:
            os.environ.setdefault("REFRACTOR_TEMPLATE_ENV", "from-dotenv")

    dotenv.load_dotenv = load_dotenv
    starlette_data = types.ModuleType("starlette.datastructures")
    starlette_data.Headers = _Headers
    starlette_exceptions = types.ModuleType("starlette.exceptions")
    starlette_exceptions.HTTPException = _HTTPException
    module = types.ModuleType("app_api.main")
    module.__package__ = "app_api"
    module.__file__ = "/project/backend/src/app_api/main.py"

    modules = {
        "fastapi": fastapi,
        "fastapi.middleware": types.ModuleType("fastapi.middleware"),
        "fastapi.middleware.cors": cors,
        "fastapi.staticfiles": static,
        "app_api": package,
        "dotenv": dotenv,
        "starlette.datastructures": starlette_data,
        "starlette.exceptions": starlette_exceptions,
        "app_api.main": module,
    }
    if observed_imports is None:
        modules["engine"] = engine_module
        modules["app_api.deps"] = deps

    class ObserverFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, fullname: str, path: object, target: object = None):
            if fullname in {"engine", "app_api.deps", "app_api.routers"}:
                return importlib.machinery.ModuleSpec(fullname, self)
            return None

        def create_module(self, spec: object):
            return None

        def exec_module(self, imported: types.ModuleType) -> None:
            observed_imports.append((imported.__name__, os.environ.get("REFRACTOR_TEMPLATE_ENV")))
            if imported.__name__ == "engine":
                imported.Engine = type(engine)
            elif imported.__name__ == "app_api.deps":
                importlib.import_module("engine")
                imported.build_engine = build_engine
            else:
                importlib.import_module("app_api.deps")
                imported.router = object()

    with patch.dict(sys.modules, modules):
        if observed_imports is None:
            exec(compile(source, str(MAIN), "exec"), module.__dict__)
            yield module
        else:
            with patch.object(sys, "meta_path", [ObserverFinder(), *sys.meta_path]):
                exec(compile(source, str(MAIN), "exec"), module.__dict__)
                yield module


class MainTemplateTests(unittest.TestCase):
    def test_falsy_injected_engine_is_used_without_a_warm_hook(self) -> None:
        class Engine:
            def __bool__(self) -> bool:
                return False

        fake = Engine()

        def build_engine() -> object:
            raise AssertionError("the injected engine must not be replaced")

        with _main_template(fake, build_engine) as module:
            app = module.create_app(fake)
            asyncio.run(_enter_lifespan(app))
        self.assertIs(app.state.engine, fake)

    def test_spa_static_files_only_fallback_for_html_navigation(self) -> None:
        with _main_template(object(), lambda: object()) as module:
            files = module.SPAStaticFiles(directory="unused")
            navigation = {"method": "GET", "headers": [(b"accept", b"text/html,application/xhtml+xml")]}
            self.assertEqual(asyncio.run(files.get_response("jobs/42", navigation)), "index.html")

            with self.assertRaises(_HTTPException):
                asyncio.run(files.get_response("api/missing", navigation))
            with self.assertRaises(_HTTPException):
                asyncio.run(files.get_response("assets/missing.js", {"method": "GET", "headers": [(b"accept", b"*/*")] }))
            with self.assertRaises(_HTTPException):
                asyncio.run(files.get_response("assets/missing.js", navigation))

    def test_loads_backend_dotenv_without_overriding_shell_settings(self) -> None:
        loaded: list[tuple[Path, bool]] = []
        with _main_template(object(), lambda: object(), loaded):
            pass
        self.assertEqual(loaded, [(Path("/project/backend/.env"), False)])

    def test_dotenv_bootstraps_before_engine_and_dependency_imports(self) -> None:
        observed: list[tuple[str, str | None]] = []
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REFRACTOR_TEMPLATE_ENV", None)
            with _main_template(object(), lambda: object(), observed_imports=observed) as module:
                asyncio.run(_enter_lifespan(module.create_app()))
        self.assertEqual(
            observed,
            [("app_api.deps", "from-dotenv"), ("engine", "from-dotenv")],
        )

    def test_dotenv_bootstraps_before_uncommented_router_imports(self) -> None:
        observed: list[tuple[str, str | None]] = []
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REFRACTOR_TEMPLATE_ENV", None)
            with _main_template(
                object(),
                lambda: object(),
                observed_imports=observed,
                include_router_import=True,
            ):
                pass
        self.assertEqual(
            observed,
            [
                ("app_api.routers", "from-dotenv"),
                ("app_api.deps", "from-dotenv"),
                ("engine", "from-dotenv"),
            ],
        )


async def _enter_lifespan(app: _FastAPI) -> None:
    async with app.lifespan(app):
        pass


class FrontendTemplateTests(unittest.TestCase):
    def test_stream_handles_crlf_frames_and_cancels_after_done(self) -> None:
        script = """
import assert from 'node:assert/strict'
import { api } from __API__

const encoder = new TextEncoder()
let cancelled = false
globalThis.fetch = async () => ({
  ok: true,
  body: new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode('event: token\\r\\ndata: {"text":\\r\\ndata: "hello"}\\r\\n\\r\\n'))
      controller.enqueue(encoder.encode('event: done\\rdata: {"finished": true}\\r\\r'))
    },
    cancel() { cancelled = true },
  }),
})
const events = []
const result = await Promise.race([
  api.stream('/chat', {}, (event) => events.push(event)).then(() => 'resolved'),
  new Promise((resolve) => setTimeout(() => resolve('timed out'), 100)),
])
assert.equal(result, 'resolved')
assert.deepEqual(events, [
  { type: 'token', data: { text: 'hello' } },
  { type: 'done', data: { finished: true } },
])
assert.equal(cancelled, true)
""".replace("__API__", json.dumps(API.as_uri()))
        result = subprocess.run(
            ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class DocumentationAndCommandTests(unittest.TestCase):
    def test_templates_document_their_actual_locations_and_platform_scope(self) -> None:
        readme = (SKILL / "assets" / "README.md").read_text()
        lan_host = (SKILL / "references" / "lan-host.md").read_text()
        self.assertIn("backend/src/<app>_api/host.py", readme)
        self.assertIn("macOS, Linux, or WSL", lan_host)

    def test_commands_are_frozen_and_use_child_pid_cleanup(self) -> None:
        makefile = MAKEFILE.read_text()
        self.assertNotIn("kill 0", makefile)
        self.assertIn("uv run --frozen pytest -q", makefile)
        self.assertIn("uv run --frozen ruff check src tests", makefile)

    def test_dev_stops_the_sibling_when_one_server_exits(self) -> None:
        makefile = MAKEFILE.read_text()
        backend = "exec uv run --frozen uvicorn <app>_api.main:app --reload --port <PORT>"
        frontend = "exec npm run dev"
        self.assertIn(backend, makefile)
        self.assertIn(frontend, makefile)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "backend").mkdir()
            (root / "frontend").mkdir()
            (root / "Makefile").write_text(
                makefile.replace(backend, "exec sh -c 'exit 7'").replace(
                    frontend,
                    "exec sh -c 'echo $$$$ > ../frontend.pid; trap \"exit 0\" TERM; while :; do sleep 1; done'",
                )
            )
            result = subprocess.run(
                ["make", "dev"], cwd=root, text=True, capture_output=True, timeout=5, check=False
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            pid = int((root / "frontend.pid").read_text())
            time.sleep(0.1)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_build_config_and_skill_guidance_are_consistent(self) -> None:
        pyproject = (SKILL / "assets" / "backend" / "pyproject-snippet.toml").read_text()
        skill = (SKILL / "SKILL.md").read_text()
        self.assertIn('target-version = "py314"', pyproject)
        self.assertIn('"src/config.py"', pyproject)
        self.assertNotIn("frontend-design skill's call — use it", skill)


if __name__ == "__main__":
    unittest.main()
