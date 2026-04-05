#!/usr/bin/env python3
"""
CPU Benchmark - Single Core and Multi-Core Performance Calculator

This program measures real CPU performance by:
1. Single-core: Running intensive calculations on one core
2. Multi-core: Utilizing all available CPU cores

Author: OpenLaoKe
Date: 2026-04-05
"""

from __future__ import annotations

import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable


def cpu_intensive_task(iterations: int) -> float:
    """
    Perform CPU-intensive calculations to measure performance.

    This uses mathematical operations that stress the CPU:
    - Floating point arithmetic
    - Trigonometric functions
    - Square roots
    - Division operations

    Args:
        iterations: Number of iterations to perform

    Returns:
        Operations per second achieved
    """
    import math

    count = 0
    start_time = time.perf_counter()

    for i in range(iterations):
        # Complex mathematical operations
        x = math.sin(i) * math.cos(i) * math.tan(i % 1000)
        y = math.sqrt(abs(x) + 1)
        z = math.log(y + 1)
        w = math.exp(min(z, 10))  # Prevent overflow

        # More operations
        a = math.sinh(w % 100)
        b = math.cosh(a % 100)
        c = math.tanh(b % 100)

        # Arithmetic operations
        result = (x + y + z + w + a + b + c) / 7
        count += 10  # 10 operations per iteration

    elapsed = time.perf_counter() - start_time
    ops_per_second = count / elapsed if elapsed > 0 else 0

    return ops_per_second


def run_single_core_benchmark(iterations: int = 1000000, warmup: int = 100000) -> dict[str, float]:
    """
    Run single-core CPU benchmark.

    Args:
        iterations: Number of iterations for main benchmark
        warmup: Number of warmup iterations

    Returns:
        Dictionary with benchmark results
    """
    print("🔥 Single-Core Benchmark")
    print("-" * 60)

    # Warmup
    print(f"  Warming up ({warmup:,} iterations)...")
    cpu_intensive_task(warmup)

    # Main benchmark
    print(f"  Running benchmark ({iterations:,} iterations)...")
    start_time = time.perf_counter()
    ops_per_second = cpu_intensive_task(iterations)
    elapsed = time.perf_counter() - start_time

    # Calculate GFLOPS (approximate, since we have ~10 ops per iteration)
    gflops = (ops_per_second * 10) / 1e9

    print(f"  ✓ Operations/second: {ops_per_second:,.0f}")
    print(f"  ✓ Time elapsed: {elapsed:.3f} seconds")
    print(f"  ✓ Estimated GFLOPS: {gflops:.3f}")
    print()

    return {
        "operations_per_second": ops_per_second,
        "elapsed_seconds": elapsed,
        "gflops": gflops,
    }


def run_multi_core_benchmark(
    iterations_per_core: int = 1000000, warmup: int = 100000
) -> dict[str, float]:
    """
    Run multi-core CPU benchmark using all available cores.

    Args:
        iterations_per_core: Number of iterations per core
        warmup: Number of warmup iterations

    Returns:
        Dictionary with benchmark results
    """
    num_cores = multiprocessing.cpu_count()
    print(f"🔥 Multi-Core Benchmark ({num_cores} cores)")
    print("-" * 60)

    # Warmup
    print(f"  Warming up all cores ({warmup:,} iterations each)...")
    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        list(executor.map(cpu_intensive_task, [warmup] * num_cores))

    # Main benchmark
    print(f"  Running benchmark on all cores ({iterations_per_core:,} iterations each)...")
    start_time = time.perf_counter()

    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        results = list(executor.map(cpu_intensive_task, [iterations_per_core] * num_cores))

    elapsed = time.perf_counter() - start_time

    # Calculate total operations
    total_ops_per_second = sum(results)
    total_operations = sum(results) * elapsed
    gflops = (total_ops_per_second * 10) / 1e9

    print(f"  ✓ Total operations/second: {total_ops_per_second:,.0f}")
    print(f"  ✓ Time elapsed: {elapsed:.3f} seconds")
    print(f"  ✓ Estimated GFLOPS: {gflops:.3f}")
    print(f"  ✓ Efficiency: {total_ops_per_second / (results[0] * num_cores) * 100:.1f}%")
    print()

    return {
        "operations_per_second": total_ops_per_second,
        "elapsed_seconds": elapsed,
        "gflops": gflops,
        "num_cores": num_cores,
        "efficiency": total_ops_per_second / (results[0] * num_cores) * 100,
    }


def calculate_cpu_score(
    single_core: dict[str, float], multi_core: dict[str, float]
) -> dict[str, float]:
    """
    Calculate overall CPU performance score.

    Args:
        single_core: Single-core benchmark results
        multi_core: Multi-core benchmark results

    Returns:
        Dictionary with CPU scores
    """
    # Normalize scores (higher is better)
    single_score = single_core["gflops"] * 100
    multi_score = multi_core["gflops"] * 100

    # Calculate parallelism efficiency
    parallelism = multi_score / single_score if single_score > 0 else 0

    # Overall score (weighted average)
    overall = single_score * 0.3 + multi_score * 0.7

    return {
        "single_core_score": single_score,
        "multi_core_score": multi_score,
        "parallelism_factor": parallelism,
        "overall_score": overall,
    }


def print_system_info() -> None:
    """Print system information."""
    import platform

    print("📊 System Information")
    print("=" * 60)
    print(f"  Platform: {platform.system()} {platform.release()}")
    print(f"  Processor: {platform.processor()}")
    print(f"  CPU Cores: {multiprocessing.cpu_count()}")
    print(f"  Python Version: {platform.python_version()}")
    print()


def main() -> None:
    """Run the complete CPU benchmark."""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " CPU Performance Benchmark - Real Calculation ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    # Print system info
    print_system_info()

    # Run benchmarks
    single_core = run_single_core_benchmark(iterations=500000)
    multi_core = run_multi_core_benchmark(iterations_per_core=500000)

    # Calculate scores
    scores = calculate_cpu_score(single_core, multi_core)

    # Print results
    print("📈 Performance Summary")
    print("=" * 60)
    print(f"  Single-Core Score: {scores['single_core_score']:.2f}")
    print(f"  Multi-Core Score: {scores['multi_core_score']:.2f}")
    print(f"  Parallelism Factor: {scores['parallelism_factor']:.2f}x")
    print(f"  Overall Score: {scores['overall_score']:.2f}")
    print()

    # Performance rating
    if scores["overall_score"] > 1000:
        rating = "🚀 Excellent"
    elif scores["overall_score"] > 500:
        rating = "✓ Good"
    elif scores["overall_score"] > 200:
        rating = "⚠️  Moderate"
    else:
        rating = "🐌 Low"

    print(f"  Performance Rating: {rating}")
    print()

    # Detailed breakdown
    print("📋 Detailed Breakdown")
    print("-" * 60)
    print(f"  Single-Core Performance:")
    print(f"    • GFLOPS: {single_core['gflops']:.3f}")
    print(f"    • Ops/sec: {single_core['operations_per_second']:,.0f}")
    print()
    print(f"  Multi-Core Performance:")
    print(f"    • GFLOPS: {multi_core['gflops']:.3f}")
    print(f"    • Ops/sec: {multi_core['operations_per_second']:,.0f}")
    print(f"    • Efficiency: {multi_core['efficiency']:.1f}%")
    print()

    print("✅ Benchmark completed successfully!")
    print()


if __name__ == "__main__":
    main()
