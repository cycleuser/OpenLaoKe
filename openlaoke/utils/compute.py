"""Compute (算力) calculation utilities for AI workloads.

This module provides comprehensive compute cost estimation for:
- GPU hardware specs and performance metrics
- Inference cost calculation
- Training cost estimation
- Multi-cloud provider comparison
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GPUType(str, Enum):
    """Supported GPU models."""

    # NVIDIA Data Center
    H100 = "h100"
    H100_SXM = "h100_sxm"
    A100_80GB = "a100_80gb"
    A100_40GB = "a100_40gb"
    A6000 = "a6000"
    L40S = "l40s"
    L4 = "l4"
    # NVIDIA Consumer
    RTX_4090 = "rtx_4090"
    RTX_3090 = "rtx_3090"
    RTX_4080_SUPER = "rtx_4080_super"
    RTX_4080 = "rtx_4080"
    RTX_4070_TI = "rtx_4070_ti"
    # AMD
    MI300X = "mi300x"
    MI250X = "mi250x"
    # Intel
    Gaudi3 = "gaudi3"


@dataclass
class GPUConfig:
    """Configuration and specs for a GPU model."""

    gpu_type: GPUType
    name: str
    fp32_tflops: float  # FP32 TFLOPS
    fp16_tflops: float  # FP16 TFLOPS
    bf16_tflops: float  # BF16 TFLOPS
    memory_gb: float  # VRAM in GB
    memory_bandwidth_gbps: float  # GB/s
    tdp_watts: int  # Thermal Design Power
    price_per_hour: float | None = None  # Cloud price per hour (USD)


class ComputeProvider(str, Enum):
    """Cloud compute providers."""

    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    LAMBDA_LABS = "lambda_labs"
    VAST_AI = "vast_ai"
    LOCAL = "local"


# GPU specifications database
GPU_DATABASE: dict[GPUType, GPUConfig] = {
    # NVIDIA Data Center GPUs
    GPUType.H100: GPUConfig(
        gpu_type=GPUType.H100,
        name="NVIDIA H100 SXM",
        fp32_tflops=67.0,
        fp16_tflops=1939.0,  # with FP8
        bf16_tflops=1979.0,
        memory_gb=80.0,
        memory_bandwidth_gbps=3350.0,
        tdp_watts=700,
        price_per_hour=30.0,
    ),
    GPUType.H100_SXM: GPUConfig(
        gpu_type=GPUType.H100_SXM,
        name="NVIDIA H100 SXM5",
        fp32_tflops=67.0,
        fp16_tflops=1939.0,
        bf16_tflops=1979.0,
        memory_gb=80.0,
        memory_bandwidth_gbps=3350.0,
        tdp_watts=700,
        price_per_hour=30.0,
    ),
    GPUType.A100_80GB: GPUConfig(
        gpu_type=GPUType.A100_80GB,
        name="NVIDIA A100 80GB SXM",
        fp32_tflops=19.5,
        fp16_tflops=312.0,
        bf16_tflops=312.0,
        memory_gb=80.0,
        memory_bandwidth_gbps=2039.0,
        tdp_watts=400,
        price_per_hour=2.50,
    ),
    GPUType.A100_40GB: GPUConfig(
        gpu_type=GPUType.A100_40GB,
        name="NVIDIA A100 40GB PCIe",
        fp32_tflops=19.5,
        fp16_tflops=312.0,
        bf16_tflops=312.0,
        memory_gb=40.0,
        memory_bandwidth_gbps=1616.0,
        tdp_watts=250,
        price_per_hour=1.50,
    ),
    GPUType.A6000: GPUConfig(
        gpu_type=GPUType.A6000,
        name="NVIDIA A6000",
        fp32_tflops=38.7,
        fp16_tflops=309.8,
        bf16_tflops=309.8,
        memory_gb=48.0,
        memory_bandwidth_gbps=768.0,
        tdp_watts=300,
        price_per_hour=1.20,
    ),
    GPUType.L40S: GPUConfig(
        gpu_type=GPUType.L40S,
        name="NVIDIA L40S",
        fp32_tflops=91.6,
        fp16_tflops=733.0,
        bf16_tflops=733.0,
        memory_gb=48.0,
        memory_bandwidth_gbps=864.0,
        tdp_watts=350,
        price_per_hour=1.50,
    ),
    GPUType.L4: GPUConfig(
        gpu_type=GPUType.L4,
        name="NVIDIA L4",
        fp32_tflops=30.3,
        fp16_tflops=242.0,
        bf16_tflops=242.0,
        memory_gb=24.0,
        memory_bandwidth_gbps=300.0,
        tdp_watts=72,
        price_per_hour=0.70,
    ),
    # Consumer GPUs
    GPUType.RTX_4090: GPUConfig(
        gpu_type=GPUType.RTX_4090,
        name="NVIDIA RTX 4090",
        fp32_tflops=82.6,
        fp16_tflops=165.2,  # using tensor cores
        bf16_tflops=165.2,
        memory_gb=24.0,
        memory_bandwidth_gbps=1008.0,
        tdp_watts=450,
        price_per_hour=None,
    ),
    GPUType.RTX_3090: GPUConfig(
        gpu_type=GPUType.RTX_3090,
        name="NVIDIA RTX 3090",
        fp32_tflops=35.6,
        fp16_tflops=142.0,
        bf16_tflops=71.0,
        memory_gb=24.0,
        memory_bandwidth_gbps=936.0,
        tdp_watts=350,
        price_per_hour=None,
    ),
    GPUType.RTX_4080_SUPER: GPUConfig(
        gpu_type=GPUType.RTX_4080_SUPER,
        name="NVIDIA RTX 4080 SUPER",
        fp32_tflops=44.9,
        fp16_tflops=88.0,
        bf16_tflops=88.0,
        memory_gb=16.0,
        memory_bandwidth_gbps=736.0,
        tdp_watts=320,
        price_per_hour=None,
    ),
    GPUType.RTX_4080: GPUConfig(
        gpu_type=GPUType.RTX_4080,
        name="NVIDIA RTX 4080",
        fp32_tflops=48.8,
        fp16_tflops=97.7,
        bf16_tflops=97.7,
        memory_gb=16.0,
        memory_bandwidth_gbps=716.0,
        tdp_watts=320,
        price_per_hour=None,
    ),
    GPUType.RTX_4070_TI: GPUConfig(
        gpu_type=GPUType.RTX_4070_TI,
        name="NVIDIA RTX 4070 Ti",
        fp32_tflops=40.0,
        fp16_tflops=80.0,
        bf16_tflops=80.0,
        memory_gb=12.0,
        memory_bandwidth_gbps=504.0,
        tdp_watts=285,
        price_per_hour=None,
    ),
    # AMD
    GPUType.MI300X: GPUConfig(
        gpu_type=GPUType.MI300X,
        name="AMD MI300X",
        fp32_tflops=163.4,
        fp16_tflops=1307.0,
        bf16_tflops=1307.0,
        memory_gb=192.0,
        memory_bandwidth_gbps=5300.0,
        tdp_watts=750,
        price_per_hour=25.0,
    ),
    GPUType.MI250X: GPUConfig(
        gpu_type=GPUType.MI250X,
        name="AMD MI250X",
        fp32_tflops=47.9,
        fp16_tflops=383.0,
        bf16_tflops=383.0,
        memory_gb=128.0,
        memory_bandwidth_gbps=3277.0,
        tdp_watts=560,
        price_per_hour=15.0,
    ),
    # Intel Gaudi
    GPUType.Gaudi3: GPUConfig(
        gpu_type=GPUType.Gaudi3,
        name="Intel Gaudi 3",
        fp32_tflops=64.0,
        fp16_tflops=1835.0,
        bf16_tflops=1835.0,
        memory_gb=128.0,
        memory_bandwidth_gbps=819.0,
        tdp_watts=900,
        price_per_hour=12.0,
    ),
}


@dataclass
class InferenceConfig:
    """Configuration for inference workload."""

    model_name: str = ""
    model_size_b: float = 7.0  # Model size in billions of parameters
    context_length: int = 4096
    batch_size: int = 1
    precision: str = "fp16"  # fp32, fp16, bf16, int8, int4
    gpu_type: GPUType = GPUType.A100_80GB
    gpu_count: int = 1
    avg_tokens_per_output: int = 256
    requests_per_hour: int = 100


@dataclass
class InferenceCost:
    """Cost breakdown for inference workload."""

    config: InferenceConfig
    gpu: GPUConfig

    # Per-request metrics
    tokens_per_second: float = 0.0
    latency_seconds: float = 0.0
    memory_required_gb: float = 0.0

    # Cost metrics
    hourly_compute_cost: float = 0.0
    cost_per_1k_tokens: float = 0.0
    cost_per_request: float = 0.0
    daily_cost: float = 0.0
    monthly_cost: float = 0.0

    # GPU utilization
    tflops_utilization: float = 0.0
    memory_utilization: float = 0.0


@dataclass
class TrainingConfig:
    """Configuration for training workload."""

    model_name: str = ""
    model_size_b: float = 7.0  # Model size in billions of parameters
    dataset_size_tokens: int = 1_000_000_000  # 1B tokens
    batch_size: int = 32
    sequence_length: int = 2048
    precision: str = "fp16"  # fp32, fp16, bf16
    gpu_type: GPUType = GPUType.A100_80GB
    gpu_count: int = 8

    # Training parameters
    epochs: int = 1
    learning_rate_factor: float = 1.0
    gradient_accumulation_steps: int = 1


@dataclass
class TrainingCost:
    """Cost breakdown for training workload."""

    config: TrainingConfig
    gpu: GPUConfig

    # Compute metrics
    total_tflops_required: float = 0.0
    estimated_training_hours: float = 0.0
    estimated_training_days: float = 0.0

    # Cost metrics
    total_compute_cost: float = 0.0
    cost_per_1k_tokens: float = 0.0
    hourly_cost: float = 0.0

    # Efficiency metrics
    tflops_per_gpu: float = 0.0
    tokens_per_second_total: float = 0.0


class ComputeCalculator:
    """Calculator for compute costs and performance estimates."""

    # FLOPs estimates for training (Chinchilla scaling laws approximation)
    TRAINING_FLOPS_PER_TOKEN = {
        "fp32": 6,  # 6 FLOPs per parameter per token (forward + backward)
        "fp16": 2,  # 2 FLOPs per parameter per token (half precision)
        "bf16": 2,  # 2 FLOPs per parameter per token (bfloat16)
    }

    # Memory estimates for model weights (in bytes per parameter)
    MEMORY_PER_PARAM = {
        "fp32": 4,
        "fp16": 2,
        "bf16": 2,
        "int8": 1,
        "int4": 0.5,
    }

    # KV cache memory per token (rough estimates)
    KV_CACHE_PER_TOKEN = {
        "fp32": 8 * 2 * 128,  # key + value, fp32, 128 heads
        "fp16": 2 * 2 * 128,
        "bf16": 2 * 2 * 128,
    }

    def __init__(self, gpu_type: GPUType = GPUType.A100_80GB):
        self.gpu_type = gpu_type
        self.gpu = GPU_DATABASE.get(gpu_type)
        if not self.gpu:
            raise ValueError(f"Unknown GPU type: {gpu_type}")

    def get_effective_tflops(self, precision: str) -> float:
        """Get effective TFLOPS for given precision."""
        precision_map = {
            "fp32": self.gpu.fp32_tflops,
            "fp16": self.gpu.fp16_tflops,
            "bf16": self.gpu.bf16_tflops,
        }
        return precision_map.get(precision, self.gpu.bf16_tflops)

    def estimate_inference_cost(self, config: InferenceConfig) -> InferenceCost:
        """Estimate inference cost for given configuration."""
        gpu = GPU_DATABASE.get(config.gpu_type, self.gpu)
        precision = config.precision

        # Calculate memory requirements
        memory_per_param = self.MEMORY_PER_PARAM.get(precision, 2)
        model_memory_gb = config.model_size_b * memory_per_param

        # KV cache memory
        kv_memory_per_token = self.KV_CACHE_PER_TOKEN.get(precision, 512)
        kv_memory_gb = (config.context_length * kv_memory_per_token * config.batch_size) / (1024**3)

        total_memory_gb = model_memory_gb + kv_memory_gb

        # Estimate tokens per second based on model size and GPU
        # Simplified model: throughput scales roughly with TFLOPs / model_size
        effective_tflops = self.get_effective_tflops(precision)
        memory_bandwidth = gpu.memory_bandwidth_gbps

        # Very rough throughput estimate
        if config.model_size_b <= 7:
            base_tps = 50  # tokens/second base rate
        elif config.model_size_b <= 13:
            base_tps = 35
        elif config.model_size_b <= 70:
            base_tps = 20
        else:
            base_tps = 10

        # Scale by GPU capability relative to A100 80GB
        gpu_scale = gpu.fp16_tflops / GPU_DATABASE[GPUType.A100_80GB].fp16_tflops
        tokens_per_second = base_tps * gpu_scale * config.gpu_count

        # Handle memory constraints
        memory_constraint = gpu.memory_gb / total_memory_gb if total_memory_gb > 0 else 1.0
        if memory_constraint < 1.0:
            tokens_per_second *= memory_constraint

        latency_seconds = (
            config.avg_tokens_per_output / tokens_per_second if tokens_per_second > 0 else 0
        )

        # Calculate costs
        hourly_compute = 0.0
        if gpu.price_per_hour:
            hourly_compute = gpu.price_per_hour * config.gpu_count

        # Cost per token (compute only, rough estimate)
        tokens_per_hour = tokens_per_second * 3600
        cost_per_1k_tokens = (hourly_compute / tokens_per_hour * 1000) if tokens_per_hour > 0 else 0

        # Total costs
        cost_per_request = cost_per_1k_tokens * config.avg_tokens_per_output / 1000
        daily_cost = hourly_compute * 24
        monthly_cost = daily_cost * 30

        # GPU utilization estimate
        tflops_needed = config.model_size_b * 2 * config.batch_size * tokens_per_second / 1e12
        tflops_utilization = (
            (tflops_needed / (effective_tflops * config.gpu_count)) * 100
            if effective_tflops > 0
            else 0
        )
        memory_utilization = (
            (total_memory_gb / (gpu.memory_gb * config.gpu_count)) * 100 if gpu.memory_gb > 0 else 0
        )

        return InferenceCost(
            config=config,
            gpu=gpu,
            tokens_per_second=tokens_per_second,
            latency_seconds=latency_seconds,
            memory_required_gb=total_memory_gb,
            hourly_compute_cost=hourly_compute,
            cost_per_1k_tokens=cost_per_1k_tokens,
            cost_per_request=cost_per_request,
            daily_cost=daily_cost,
            monthly_cost=monthly_cost,
            tflops_utilization=min(tflops_utilization, 100.0),
            memory_utilization=min(memory_utilization, 100.0),
        )

    def estimate_training_cost(self, config: TrainingConfig) -> TrainingCost:
        """Estimate training cost for given configuration."""
        gpu = GPU_DATABASE.get(config.gpu_type, self.gpu)
        precision = config.precision

        # Calculate FLOPs required
        flops_per_token = self.TRAINING_FLOPS_PER_TOKEN.get(precision, 2)
        model_size = config.model_size_b * 1e9  # Convert to actual parameters

        # Total FLOPs = 6 * model_size * dataset_size * epochs (approx)
        # 6 = 2 (forward) + 4 (backward) for FP32, or 2 for FP16/BF16
        total_flops = flops_per_token * model_size * config.dataset_size_tokens * config.epochs
        total_tflops = total_flops / 1e12

        # Effective GPU TFLOPS (accounting for practical efficiency ~50% for training)
        effective_tflops = self.get_effective_tflops(precision) * config.gpu_count * 0.5

        # Training time
        training_seconds = total_tflops / effective_tflops if effective_tflops > 0 else 0
        training_hours = training_seconds / 3600
        training_days = training_hours / 24

        # Costs
        hourly_cost = 0.0
        if gpu.price_per_hour:
            hourly_cost = gpu.price_per_hour * config.gpu_count

        total_cost = hourly_cost * training_hours

        # Cost per token
        total_tokens = config.dataset_size_tokens * config.epochs
        cost_per_1k_tokens = (total_cost / total_tokens * 1000) if total_tokens > 0 else 0

        # Efficiency metrics
        tflops_per_gpu = (
            total_tflops / training_hours / config.gpu_count if training_hours > 0 else 0
        )

        # Throughput
        tokens_per_second = total_tokens / training_seconds if training_seconds > 0 else 0

        return TrainingCost(
            config=config,
            gpu=gpu,
            total_tflops_required=total_tflops,
            estimated_training_hours=training_hours,
            estimated_training_days=training_days,
            total_compute_cost=total_cost,
            cost_per_1k_tokens=cost_per_1k_tokens,
            hourly_cost=hourly_cost,
            tflops_per_gpu=tflops_per_gpu,
            tokens_per_second_total=tokens_per_second,
        )

    def compare_cloud_providers(
        self, gpu_type: GPUType, hours: float, providers: list[ComputeProvider] | None = None
    ) -> dict[str, float]:
        """Compare costs across cloud providers for given GPU and hours."""
        if providers is None:
            providers = [
                ComputeProvider.AWS,
                ComputeProvider.GCP,
                ComputeProvider.AZURE,
                ComputeProvider.LAMBDA_LABS,
                ComputeProvider.VAST_AI,
            ]

        gpu = GPU_DATABASE.get(gpu_type)
        if not gpu or not gpu.price_per_hour:
            return {}

        # Provider-specific pricing adjustments (approximate)
        provider_multipliers = {
            "aws": 1.0,
            "gcp": 0.95,
            "azure": 1.05,
            "lambda_labs": 0.85,
            "vast_ai": 0.6,
            "local": 0.0,  # Electricity only
        }

        base_hourly = gpu.price_per_hour
        results = {}

        for provider in providers:
            provider_key = provider.value
            if provider == ComputeProvider.LOCAL:
                # Estimate electricity cost (~0.10 per kWh, GPU uses ~0.35 kWh)
                results[provider_key] = hours * 0.35 * 0.10
            else:
                multiplier = provider_multipliers.get(provider_key, 1.0)
                results[provider_key] = hours * base_hourly * multiplier

        return results


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format currency amount."""
    if currency == "USD":
        return f"${amount:.4f}"
    return f"{amount:.4f} {currency}"


def format_duration(hours: float) -> str:
    """Format duration in human-readable format."""
    if hours < 1:
        return f"{hours * 60:.1f} minutes"
    elif hours < 24:
        return f"{hours:.1f} hours"
    elif hours < 168:  # 1 week
        days = hours / 24
        return f"{days:.1f} days ({hours:.1f} hours)"
    else:
        weeks = hours / 168
        return f"{weeks:.1f} weeks"


def estimate_model_vram(
    model_size_b: float,
    precision: str = "fp16",
    include_kv_cache: bool = True,
    max_context_length: int = 4096,
    batch_size: int = 1,
) -> dict[str, float]:
    """Estimate VRAM requirements for a model.

    Returns:
        Dictionary with memory breakdown in GB.
    """
    memory_per_param = ComputeCalculator.MEMORY_PER_PARAM.get(precision, 2)

    # Model weights
    weights_gb = model_size_b * memory_per_param

    # Activations (rough estimate: ~2x model size for training)
    activations_gb = model_size_b * memory_per_param * 2

    # KV cache (per token)
    kv_per_token = ComputeCalculator.KV_CACHE_PER_TOKEN.get(precision, 512) / (1024**3)
    kv_cache_gb = kv_per_token * max_context_length * batch_size if include_kv_cache else 0

    # Gradient optimizer states (training only, fp32 copies)
    optimizer_gb = model_size_b * 4  # Adam optimizer: 2 states per parameter

    return {
        "weights": weights_gb,
        "activations": activations_gb,
        "kv_cache": kv_cache_gb,
        "optimizer": optimizer_gb,
        "total_inference": weights_gb + kv_cache_gb,
        "total_training": weights_gb + activations_gb + kv_cache_gb + optimizer_gb,
    }


def print_inference_report(cost: InferenceCost) -> str:
    """Generate a formatted inference cost report."""
    cfg = cost.config
    gpu = cost.gpu

    lines = [
        "=" * 60,
        "INFERENCE COST REPORT",
        "=" * 60,
        "",
        "Model Configuration:",
        f"  Model Size: {cfg.model_size_b}B parameters",
        f"  Precision: {cfg.precision}",
        f"  Context Length: {cfg.context_length:,} tokens",
        f"  Batch Size: {cfg.batch_size}",
        "",
        "Hardware:",
        f"  GPU: {gpu.name}",
        f"  GPU Count: {cfg.gpu_count}",
        f"  Memory per GPU: {gpu.memory_gb} GB",
        "",
        "Performance Estimates:",
        f"  Throughput: {cost.tokens_per_second:.1f} tokens/second",
        f"  Latency: {cost.latency_seconds:.3f} seconds",
        f"  Memory Required: {cost.memory_required_gb:.2f} GB",
        "",
        "GPU Utilization:",
        f"  TFLOPS Utilization: {cost.tflops_utilization:.1f}%",
        f"  Memory Utilization: {cost.memory_utilization:.1f}%",
        "",
        "Cost Estimates:",
        f"  Hourly Compute: {format_currency(cost.hourly_compute_cost)}",
        f"  Cost per 1K tokens: {format_currency(cost.cost_per_1k_tokens)}",
        f"  Cost per request: {format_currency(cost.cost_per_request)}",
        f"  Daily Cost: {format_currency(cost.daily_cost)}",
        f"  Monthly Cost: {format_currency(cost.monthly_cost)}",
        "=" * 60,
    ]
    return "\n".join(lines)


def print_training_report(cost: TrainingCost) -> str:
    """Generate a formatted training cost report."""
    cfg = cost.config
    gpu = cost.gpu

    lines = [
        "=" * 60,
        "TRAINING COST REPORT",
        "=" * 60,
        "",
        "Model Configuration:",
        f"  Model Size: {cfg.model_size_b}B parameters",
        f"  Precision: {cfg.precision}",
        f"  Dataset Size: {cfg.dataset_size_tokens / 1e9:.1f}B tokens",
        f"  Epochs: {cfg.epochs}",
        f"  Batch Size: {cfg.batch_size}",
        f"  Sequence Length: {cfg.sequence_length}",
        "",
        "Hardware:",
        f"  GPU: {gpu.name}",
        f"  GPU Count: {cfg.gpu_count}",
        f"  Total VRAM: {gpu.memory_gb * cfg.gpu_count} GB",
        "",
        "Compute Requirements:",
        f"  Total TFLOPS: {cost.total_tflops_required:,.0f}",
        f"  Effective TFLOPS/GPU: {cost.tflops_per_gpu:,.1f}",
        "",
        "Time Estimates:",
        f"  Training Time: {format_duration(cost.estimated_training_hours)}",
        f"  Throughput: {cost.tokens_per_second_total:,.0f} tokens/sec",
        "",
        "Cost Estimates:",
        f"  Hourly Cost: {format_currency(cost.hourly_cost)}",
        f"  Total Cost: {format_currency(cost.total_compute_cost)}",
        f"  Cost per 1K tokens: {format_currency(cost.cost_per_1k_tokens)}",
        "=" * 60,
    ]
    return "\n".join(lines)


# Convenience function for quick calculations
def quick_estimate(
    model_size_b: float, gpu_type: GPUType = GPUType.A100_80GB, mode: str = "inference", **kwargs
) -> TrainingCost | InferenceCost:
    """Quick estimate for common scenarios.

    Args:
        model_size_b: Model size in billions of parameters
        gpu_type: GPU type to use
        mode: 'inference' or 'training'
        **kwargs: Additional configuration parameters

    Returns:
        TrainingCost or InferenceCost object
    """
    calc = ComputeCalculator(gpu_type)

    if mode == "inference":
        config = InferenceConfig(model_size_b=model_size_b, gpu_type=gpu_type, **kwargs)
        return calc.estimate_inference_cost(config)
    else:
        config = TrainingConfig(model_size_b=model_size_b, gpu_type=gpu_type, **kwargs)
        return calc.estimate_training_cost(config)


if __name__ == "__main__":
    # Example usage
    print("GPU Compute Calculator - Example Usage\n")

    # Example 1: Estimate inference cost for a 7B model on A100
    print("Example 1: 7B Model Inference on A100 80GB")
    print("-" * 40)
    inference_cost = quick_estimate(
        model_size_b=7,
        gpu_type=GPUType.A100_80GB,
        mode="inference",
        context_length=4096,
        avg_tokens_per_output=256,
        requests_per_hour=100,
    )
    print(print_inference_report(inference_cost))
    print()

    # Example 2: Estimate training cost for a 70B model on H100 cluster
    print("Example 2: 70B Model Training on H100 Cluster (8 GPUs)")
    print("-" * 40)
    training_cost = quick_estimate(
        model_size_b=70,
        gpu_type=GPUType.H100,
        mode="training",
        gpu_count=8,
        dataset_size_tokens=1_000_000_000,  # 1B tokens
        epochs=1,
    )
    print(print_training_report(training_cost))
    print()

    # Example 3: VRAM estimation
    print("Example 3: VRAM Requirements for 13B Model")
    print("-" * 40)
    vram = estimate_model_vram(13, precision="fp16", max_context_length=4096, batch_size=1)
    print(f"  Weights (FP16): {vram['weights']:.1f} GB")
    print(f"  KV Cache (4K ctx): {vram['kv_cache']:.2f} GB")
    print(f"  Total Inference: {vram['total_inference']:.1f} GB")
    print(f"  Total Training: {vram['total_training']:.1f} GB")
    print()

    # Example 4: Compare cloud providers
    print("Example 4: Cloud Provider Comparison (H100, 24 hours)")
    print("-" * 40)
    calc = ComputeCalculator(GPUType.H100)
    comparison = calc.compare_cloud_providers(GPUType.H100, hours=24)
    for provider, cost in comparison.items():
        print(f"  {provider.value}: {format_currency(cost)}")
