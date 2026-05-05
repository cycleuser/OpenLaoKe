"""Local GGUF model manager for downloading and managing built-in models from ModelScope."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from openlaoke.utils.install_logger import get_install_logger

DEFAULT_MODEL_DIR = os.path.expanduser("~/.openlaoke/models")

CUSTOM_MODELS_REGISTRY = os.path.join(DEFAULT_MODEL_DIR, "custom_models.json")

MODELSCOPE_API_BASE = "https://www.modelscope.cn"


def _normalize_tags(tags: Any) -> list[str]:
    if isinstance(tags, list):
        return [str(t) for t in tags]
    if isinstance(tags, str):
        return [tags]
    return []


# 已知的 GGUF 模型发布者/组织
GGUF_SOURCE_ORGS = [
    # 官方组织
    "Qwen",
    "LLM-Research",
    "AI-ModelScope",
    "modelscope",
    "google",
    # 社区 GGUF 转换者
    "bartowski",
    "TheBloke",
    "MaziyarPanahi",
    "gguf-org",
    "unsloth",
    "second-state",
]

DEFAULT_BUILTIN_MODELS: dict[str, dict[str, str]] = {}


@dataclass
class ModelInfo:
    """Information about a local model."""

    model_id: str
    name: str
    filename: str
    path: str
    size_mb: float
    description: str
    modelscope_id: str = ""
    tags: list[str] = field(default_factory=list)
    downloaded: bool = False


@dataclass
class LocalModelManager:
    """Manages local GGUF models with ModelScope integration."""

    model_dir: str = DEFAULT_MODEL_DIR
    logger: Any = None
    _models: dict[str, ModelInfo] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.logger is None:
            self.logger = get_install_logger()
        os.makedirs(self.model_dir, exist_ok=True)
        self._scan_models()

    def _scan_models(self) -> None:
        """Scan model directory for existing models (built-in + custom)."""
        for model_id, model_config in DEFAULT_BUILTIN_MODELS.items():
            filepath = os.path.join(self.model_dir, model_config["filename"])
            downloaded = os.path.exists(filepath)
            self._models[model_id] = ModelInfo(
                model_id=model_id,
                name=model_config["name"],
                filename=model_config["filename"],
                path=filepath,
                size_mb=float(model_config["size_mb"]),
                description=model_config["description"],
                modelscope_id=model_config["modelscope_id"],
                tags=_normalize_tags(model_config.get("tags", [])),
                downloaded=downloaded,
            )
        self._load_custom_models_registry()

    def _load_custom_models_registry(self) -> None:
        """Load custom models from the persistent JSON registry."""
        registry_path = os.path.join(self.model_dir, "custom_models.json")
        if not os.path.exists(registry_path):
            return
        try:
            with open(registry_path) as f:
                custom_models: dict[str, dict[str, Any]] = json.load(f)
            for model_id, model_data in custom_models.items():
                if model_id in self._models:
                    continue
                filepath = os.path.join(self.model_dir, str(model_data["filename"]))
                self._models[model_id] = ModelInfo(
                    model_id=str(model_data["model_id"]),
                    name=str(model_data["name"]),
                    filename=str(model_data["filename"]),
                    path=filepath,
                    size_mb=float(model_data["size_mb"]),
                    description=str(model_data.get("description", "")),
                    modelscope_id=str(model_data.get("modelscope_id", "")),
                    tags=list(model_data.get("tags", [])),
                    downloaded=os.path.exists(filepath),
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    def _save_custom_models_registry(self) -> None:
        """Save custom models (non-builtin) to the persistent JSON registry."""
        builtin_ids = set(DEFAULT_BUILTIN_MODELS.keys())
        custom_models = {}
        for model_id, model_info in self._models.items():
            if model_id not in builtin_ids:
                custom_models[model_id] = {
                    "model_id": model_info.model_id,
                    "name": model_info.name,
                    "filename": model_info.filename,
                    "path": model_info.path,
                    "size_mb": model_info.size_mb,
                    "description": model_info.description,
                    "modelscope_id": model_info.modelscope_id,
                    "tags": model_info.tags,
                    "downloaded": model_info.downloaded,
                }
        registry_path = os.path.join(self.model_dir, "custom_models.json")
        try:
            with open(registry_path, "w") as f:
                json.dump(custom_models, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def list_models(self) -> list[ModelInfo]:
        """List all available models (built-in + custom)."""
        return list(self._models.values())

    def get_model(self, model_id: str) -> ModelInfo | None:
        """Get model info by ID."""
        return self._models.get(model_id)

    def is_downloaded(self, model_id: str) -> bool:
        """Check if a model is downloaded."""
        model = self._models.get(model_id)
        if model:
            return model.downloaded
        return False

    async def search_modelscope(self, query: str) -> list[dict[str, Any]]:
        """Search for GGUF models on ModelScope across multiple organizations."""
        try:
            from modelscope.hub.api import HubApi

            api = HubApi()
            results = []
            query_lower = query.lower()

            for org in GGUF_SOURCE_ORGS:
                try:
                    result = api.list_models(org, page_number=1, page_size=200)
                    if result and isinstance(result, dict) and "Models" in result:
                        for m in result["Models"]:
                            name = m.get("Name", "")
                            path = m.get("Path", "")
                            name_lower = name.lower()

                            # 检查是否匹配查询且是 GGUF 模型
                            if query_lower in name_lower and "gguf" in name_lower:
                                model_id = f"{path}/{name}"
                                # 检查是否有 GGUF 文件
                                try:
                                    files = api.get_model_files(model_id, revision="master")
                                    if isinstance(files, list):
                                        gguf_files = [
                                            f for f in files if f.get("Name", "").endswith(".gguf")
                                        ]
                                        if gguf_files:
                                            # 找最小的 GGUF 文件（通常是 Q4 量化）
                                            smallest = min(
                                                gguf_files, key=lambda x: x.get("Size", 0)
                                            )
                                            size_mb = smallest.get("Size", 0) / (1024 * 1024)

                                            results.append(
                                                {
                                                    "ModelId": model_id,
                                                    "Name": name,
                                                    "Downloads": m.get("Downloads", 0),
                                                    "Description": m.get("Description", "") or "",
                                                    "Path": path,
                                                    "GGUFFiles": gguf_files,
                                                    "SmallestFile": smallest,
                                                    "SmallestSizeMB": size_mb,
                                                }
                                            )
                                except Exception:
                                    continue
                except Exception:
                    continue

            # 按下载量排序
            return sorted(results, key=lambda x: x["Downloads"], reverse=True)

        except Exception as e:
            self.logger.error(f"Failed to search ModelScope: {e}")
            return []

    async def get_modelscope_files(self, model_id: str) -> list[dict[str, Any]]:
        """Get file list for a ModelScope model."""
        try:
            from modelscope.hub.api import HubApi

            api = HubApi()
            files = api.get_model_files(model_id, revision="master")
            if isinstance(files, list):
                return files
            return []
        except Exception as e:
            self.logger.error(f"Failed to get model files: {e}")
            return []

    async def download_from_modelscope(
        self,
        model_id: str,
        filename: str,
        progress_callback: Callable | None = None,
    ) -> str:
        """Download a model file from ModelScope, replacing old quantization if exists."""
        filepath = os.path.join(self.model_dir, filename)

        if os.path.exists(filepath):
            self.logger.info(f"Model already downloaded: {filename}")
            return filepath

        # Replace old quantization from the same ModelScope repo
        old_model_ids = []
        for mid, minfo in list(self._models.items()):
            if mid.startswith("custom:") and minfo.modelscope_id == model_id and minfo.downloaded:
                old_model_ids.append(mid)
                if os.path.exists(minfo.path):
                    self.logger.info(f"Replacing old quantization: {minfo.filename}")
                    os.remove(minfo.path)

        for old_id in old_model_ids:
            del self._models[old_id]
        if old_model_ids:
            self._save_custom_models_registry()

        download_url = f"{MODELSCOPE_API_BASE}/api/v1/models/{model_id}/repo?Revision=master&FilePath={filename}"

        self.logger.info(f"Downloading {filename} from ModelScope...")
        self.logger.info(f"ModelScope ID: {model_id}")

        temp_path = filepath + ".tmp"

        try:
            async with (
                httpx.AsyncClient(timeout=httpx.Timeout(3600.0, connect=60.0)) as client,
                client.stream("GET", download_url, follow_redirects=True) as response,
            ):
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(temp_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress, downloaded, total_size)

            os.rename(temp_path, filepath)
            self.logger.info(f"Downloaded: {filename}")
            for m in self._models.values():
                if m.filename == filename:
                    m.downloaded = True
                    self._save_custom_models_registry()
                    break
            return filepath

        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            self.logger.error(f"Failed to download {filename}: {e}")
            raise

    async def download_model(
        self,
        model_id: str,
        progress_callback: Callable | None = None,
    ) -> str:
        """Download a model with progress tracking."""
        if model_id in DEFAULT_BUILTIN_MODELS:
            model_config = DEFAULT_BUILTIN_MODELS[model_id]
            return await self.download_from_modelscope(
                model_config["modelscope_id"],
                model_config["filename"],
                progress_callback,
            )
        else:
            raise ValueError(
                f"Unknown model: {model_id}. Use 'openlaoke model search' to find models."
            )

    def add_custom_model(
        self,
        model_id: str,
        name: str,
        modelscope_id: str,
        filename: str,
        size_mb: float,
        description: str = "",
        tags: list[str] | None = None,
    ) -> None:
        """Add a custom model from ModelScope search results, replacing old quantization if exists."""
        # Replace old quantization from the same repo
        old_model_ids = []
        for mid, minfo in list(self._models.items()):
            if (
                mid.startswith("custom:")
                and minfo.modelscope_id == modelscope_id
                and mid != model_id
            ):
                old_model_ids.append(mid)
                if minfo.downloaded and os.path.exists(minfo.path):
                    self.logger.info(f"Removing old quantization: {minfo.filename}")
                    os.remove(minfo.path)

        for old_id in old_model_ids:
            del self._models[old_id]

        filepath = os.path.join(self.model_dir, filename)
        downloaded = os.path.exists(filepath)

        self._models[model_id] = ModelInfo(
            model_id=model_id,
            name=name,
            filename=filename,
            path=filepath,
            size_mb=size_mb,
            description=description,
            modelscope_id=modelscope_id,
            tags=tags or [],
            downloaded=downloaded,
        )
        self._save_custom_models_registry()

    def remove_model(self, model_id: str) -> bool:
        """Remove a downloaded model."""
        model = self._models.get(model_id)
        if not model or not model.downloaded:
            return False

        try:
            if os.path.exists(model.path):
                os.remove(model.path)
                self.logger.info(f"Removed: {model.name}")
                model.downloaded = False
                self._save_custom_models_registry()
                return True
        except OSError as e:
            self.logger.error(f"Failed to remove {model_id}: {e}")
            raise

        return False

    def get_default_model(self) -> str | None:
        """Get the first downloaded model, or recommend qwen3:0.6b."""
        for model in self._models.values():
            if model.downloaded:
                return model.model_id

        return "qwen3:0.6b"

    def get_model_path(self, model_id: str) -> str | None:
        """Get the file path for a model.

        Looks up the model registry first. If not found and the model_id
        looks like a custom model (contains '/'), attempts to find the
        GGUF file on disk directly.
        """
        model = self._models.get(model_id)
        if model and model.downloaded:
            if os.path.exists(model.path):
                return model.path
            model.downloaded = False
            return None

        if "/" in model_id:
            for f in os.listdir(self.model_dir):
                if f.endswith(".gguf") and not f.endswith(".tmp"):
                    filepath = os.path.join(self.model_dir, f)
                    if model_id.split("/")[-1].lower().replace("-", "").replace(
                        ".", ""
                    ) in f.lower().replace("-", "").replace(".", ""):
                        self.add_custom_model(
                            model_id=model_id.replace("/", "-")
                            if not model_id.startswith("custom:")
                            else model_id,
                            name=model_id,
                            modelscope_id=model_id,
                            filename=f,
                            size_mb=os.path.getsize(filepath) / (1024 * 1024),
                            description=f"Custom model from ModelScope: {model_id}",
                            tags=["custom"],
                        )
                        return filepath
        return None

    def get_disk_usage(self) -> dict[str, float]:
        """Get disk usage statistics."""
        total_size = 0
        downloaded_count = 0

        for model in self._models.values():
            if model.downloaded and os.path.exists(model.path):
                total_size += os.path.getsize(model.path)
                downloaded_count += 1

        return {
            "total_mb": total_size / (1024 * 1024),
            "models_downloaded": downloaded_count,
            "models_available": len(self._models),
        }
