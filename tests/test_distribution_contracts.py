"""Release artifact contracts that do not require a running Docker daemon."""

import json
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.fast
def test_packaging_metadata_uses_current_spdx_license_contract() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["license"] == "MIT"
    assert "License :: OSI Approved :: MIT License" not in pyproject["project"]["classifiers"]
    assert "setuptools>=77.0" in pyproject["build-system"]["requires"]


@pytest.mark.fast
def test_api_extra_includes_multipart_runtime_required_by_upload_routes() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "python-multipart>=0.0.9" in pyproject["project"]["optional-dependencies"]["api"]


@pytest.mark.fast
def test_default_install_is_lightweight_and_feature_extras_restore_runtime_capabilities() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    base_dependencies = project["dependencies"]
    extras = project["optional-dependencies"]

    assert not any(dependency.startswith("chromadb") for dependency in base_dependencies)
    assert not any(
        dependency.startswith("sentence-transformers") for dependency in base_dependencies
    )
    assert not any(dependency.startswith("markitdown") for dependency in base_dependencies)

    assert "markitdown>=0.0.1" in extras["documents"]
    assert "chromadb>=0.4.0" in extras["vector"]
    assert "sentence-transformers>=2.2.0" in extras["vector"]
    assert "leann>=0.3.7" in extras["leann"]
    assert not any(dependency.startswith("leann-vector") for dependency in extras["leann"])
    assert "dochris[api,documents,pdf,vector]" in extras["standard"]
    assert "dochris[api,audio,documents,leann,ocr,ollama,pdf,vector]" in extras["all"]
    assert not any("dev" in dependency for dependency in extras["all"])


@pytest.mark.fast
def test_docker_core_skips_torch_while_api_keeps_cpu_vector_runtime() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    builder = dockerfile.split(" AS builder", maxsplit=1)[1].split(" AS runtime", maxsplit=1)[0]

    assert (
        'api|all) pip install $PIP_LARGE_DOWNLOAD_OPTIONS "torch==${TORCH_VERSION}+cpu"' in builder
    )
    assert 'api)   pip install $PIP_LARGE_DOWNLOAD_OPTIONS ".[standard]"' in builder


@pytest.mark.fast
def test_frontend_declares_the_node_22_toolchain_used_by_ci_and_docker() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))

    assert package["engines"]["node"] == ">=22.13 <23"
    assert (ROOT / ".nvmrc").read_text(encoding="utf-8").strip() == "22"


@pytest.mark.fast
def test_git_paths_do_not_collide_on_case_insensitive_filesystems() -> None:
    """A clean clone must materialize every tracked path on macOS and Windows."""
    if not (ROOT / ".git").exists():
        pytest.skip("Git index is unavailable in a source distribution")

    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = [path for path in result.stdout.decode().split("\0") if path]
    by_casefold: dict[str, list[str]] = {}
    for path in paths:
        by_casefold.setdefault(path.casefold(), []).append(path)

    collisions = [group for group in by_casefold.values() if len(group) > 1]
    assert collisions == []


@pytest.mark.fast
def test_compose_api_profile_includes_production_web() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    web = compose["services"]["web"]

    assert web["profiles"] == ["api"]
    assert web["build"]["dockerfile"] == "frontend/Dockerfile"
    assert web["image"] == "dochris:web"
    assert web["depends_on"]["api"]["condition"] == "service_healthy"
    assert web["ports"] == ["127.0.0.1:${WEB_PORT:-3000}:80"]
    assert web["healthcheck"]["test"][-1] == "http://127.0.0.1/healthz"


@pytest.mark.fast
def test_compose_local_dev_auth_is_explicit_and_ports_are_loopback_only() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert (
        "DOCHRIS_ALLOW_UNAUTHENTICATED=${DOCHRIS_ALLOW_UNAUTHENTICATED:-true}"
        in services["api"]["environment"]
    )
    assert services["api"]["ports"] == ["127.0.0.1:${API_PORT:-8000}:8000"]
    assert services["web"]["ports"] == ["127.0.0.1:${WEB_PORT:-3000}:80"]
    # 应用使用嵌入式 PersistentClient（数据在 kb-data 卷），无独立 chroma 服务
    assert "chromadb" not in services


@pytest.mark.fast
def test_compose_api_healthcheck_uses_the_python_runtime_instead_of_removed_curl() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    healthcheck = compose["services"]["api"]["healthcheck"]["test"]

    assert healthcheck[:2] == ["CMD", "python"]
    assert "urllib.request.urlopen" in healthcheck[-1]
    assert "http://127.0.0.1:8000/ready" in healthcheck[-1]
    assert "curl" not in healthcheck


@pytest.mark.fast
def test_frontend_image_builds_spa_and_proxies_api() -> None:
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")

    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert "COPY --from=builder /app/dist /usr/share/nginx/html" in dockerfile
    assert "location /api/" in nginx
    assert "proxy_pass http://api:8000" in nginx
    assert "try_files $uri $uri/ /index.html" in nginx
    assert "location = /healthz" in nginx


@pytest.mark.fast
def test_runtime_image_installs_feature_system_packages_only_for_all_target() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime = dockerfile.split(" AS runtime", maxsplit=1)[1]

    assert "libgl1-mesa-glx" not in dockerfile
    assert 'all) runtime_packages="' in runtime
    assert "poppler-utils" in runtime
    assert "tesseract-ocr" in runtime
    assert "ffmpeg" in runtime
    assert "libtesseract-dev" not in runtime
    assert 'if [ -n "$runtime_packages" ]' in runtime


@pytest.mark.fast
def test_python_image_reuses_dependency_layers_and_retries_apt_downloads() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    builder = dockerfile.split(" AS builder", maxsplit=1)[1].split(" AS runtime", maxsplit=1)[0]
    runtime = dockerfile.split(" AS runtime", maxsplit=1)[1]

    assert builder.index("apt-get") < builder.index("ARG BUILD_TARGET")
    assert runtime.index("ARG BUILD_TARGET") < runtime.index("apt-get")
    assert dockerfile.count("apt-get -o Acquire::Retries=3 update") == 2
    assert dockerfile.count("apt-get -o Acquire::Retries=3 install") == 2


@pytest.mark.fast
def test_python_builder_caches_pip_downloads_and_retries_unstable_networks() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    builder = dockerfile.split(" AS builder", maxsplit=1)[1].split(" AS runtime", maxsplit=1)[0]

    assert 'PIP_NETWORK_OPTIONS="--retries 10 --timeout 60"' in builder
    assert 'PIP_LARGE_DOWNLOAD_OPTIONS="--retries 10 --resume-retries 10 --timeout 60"' in builder
    assert builder.count("--mount=type=cache,target=/root/.cache/pip") == 3
    assert "pip install --no-cache-dir" not in builder


@pytest.mark.fast
def test_cpu_image_preinstalls_cpu_only_torch_before_project_dependencies() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    builder = dockerfile.split(" AS builder", maxsplit=1)[1].split(" AS runtime", maxsplit=1)[0]

    assert "ARG TORCH_VERSION=2.13.0" in builder
    assert '"torch==${TORCH_VERSION}+cpu"' in builder
    assert "--index-url https://download.pytorch.org/whl/cpu" in builder
    project_install = "RUN --mount=type=cache,target=/root/.cache/pip <<EOF"
    assert builder.index('"torch==${TORCH_VERSION}+cpu"') < builder.index(project_install)


@pytest.mark.fast
def test_compose_has_no_standalone_chroma_server() -> None:
    """应用使用嵌入式 PersistentClient（kb-data 卷）；独立 chroma 服务是死重，禁止回归。"""
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    assert "chromadb" not in compose["services"]
    assert not any("kb-chroma" in str(v) for v in compose.get("volumes", {}))
    # 数据仍通过 kb-data 持久化
    assert "kb-data:/app/data" in compose["services"]["api"]["volumes"]


@pytest.mark.fast
def test_docs_ci_treats_all_mkdocs_warnings_as_release_failures() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    )
    run_commands = [
        step["run"]
        for step in workflow["jobs"]["build"]["steps"]
        if isinstance(step, dict) and "run" in step
    ]

    assert "mkdocs build --strict" in run_commands
