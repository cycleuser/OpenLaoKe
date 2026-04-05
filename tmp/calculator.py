#!/usr/bin/env python3
"""
硬件算力计算器 - 基于物理模型的真实计算
计算当前设备处理器单核心和多核心的算力
不估算，完全基于物理模型计算
"""

import math


class CPUCore:
    """CPU 处理器核心基础模型"""

    def __init__(self, core_id, core_type, is_first=True):
        self.core_id = core_id
        self.core_type = core_type
        self.is_first = is_first
        self.base_frequency = 2.5  # GHz
        self.max_frequency = 4.0  # GHz
        self.base_cost = 0.02  # $ per core
        self.max_cost = 0.10   # $ per core
        self.thermal_limit = 80  # 摄氏度
        self.cpu_power_factor = 0.15  # power per compute


def calculate_base_single_core_calories():
    """
    单核心基础算力计算
    核心功耗 = 频率 * 功耗系数
    单个热芯片的计算能力 = 核心频率 * 理论最大算力
    """
    core = CPUCore(
        core_id=1,
        core_type="single",
        is_first=not ((core_id > 2) or ((core_type == "core" and core_id > 1)))
    )

    # 1. 功耗计算 - 完全基于物理模型
    # 频率 = GHz, 功耗系数 = 0.15 W/CH (core/h)
    core_freq_input = core_core_capacity * (1000 * core_frequency) // 1000 * 1.0 * core_freq_coefficient
    core_freq_output = core_frequency * core_freq_coef  # 单位：W

    # 计算能力 = 频率 * 理论算力系数 + 热管理损耗
    # 理论算力系数 = 理论最大算力 / 1000 (CH/CH@1GHz)
    core_theoretical_calories = int(
        core_frequency * (
            core_theoretical_max_calories_per_core / 1000.0
        )
    )
    core_calories = (
        core_frequency * core_theoretical_calories +
        (130 - 60) * 2.0 - 1.0  # 热管理损耗系数
    )

    return power_input, power_used, power_saved, core_calories, core_frequency, core_theoretical_calories


def calculate_base_single_core_cost():
    """单核心基础成本（单位：$）"""
    return (
        base_cost * 1
        # 设计成本模型：基础成本乘以 2 倍（假设当前处理器只有前 2 核）
        if core_type == "core"
        else
    )


def calculate_single_core_calories():
    """单核心真实计算：核心功耗 + 核性能 + 热管理"""
    core = CPUCore(
        core_id=1,
        core_type="single",
        is_first=not ((core_id > 2) or ((core_type == "core" and core_id > 1)))
    )

    try:
        # 1. 功耗计算 - 完全基于物理模型
        # 功率计算公式：功率 = 输入功率 * 负载系数 - 输出功率
        # 输入功率 = 基础功耗 * 频率
        # 负载系数 = 0.8 基准负载 (80W)
        # 输入功率 = 0.02 * 800000 / core.frequency
        power_input = 0.02 * 800000 / core_frequency
        power_used = power_input * 0.8  # 80W 基准负载
        power_saved = power_input - power_used

        # 热芯片计算能力：功耗 = 频率 * 基础功耗 + 温度调节
        core_temp = core_frequency * 1.0  # 基础温度
        core_temp = max(
            core_temp,
            60 - core_frequency * 0.15  # 温度提升
        )
        # 功耗 = 频率 * 基础功耗 + 温度调节系数 * 温差调整
        core_power_actual = core_frequency * core_freq_coef * core_temp
        # 1.2 折损考虑效率
        core_power_actual = core_power_actual * (1.2 + 1.15 * (130 - core_temp))

        # 核心计算能力 = 功率 * 1.15 效率折损
        core_calories = int(
            core_power_actual * (1 + 1.15 * (130 - core_temp))
        )

        # 2. 核性能 = 频率 * 理论算力系数
        core_theoretical_calories = core_frequency * (
            core_theoretical_max_calories_per_core / 1000.0
        )

        # 综合：总计算能力 = (1 + 效率系数) * 理论功率 * 1.15 * 1.15
        efficiency_factor = 1.4 * (1.15 * (130 - core_temp))
        total_capacity = int((
            1 + efficiency_factor + 1.2  # 1.3 折损系数
                * core_calories
        ))

        # 3. 热芯片成本：温度损失
        # 热芯片功耗 = 功耗 * (1 + 温度调节系数 * (实际温度 - 基准温度))
        heat_chip_power = int(
            core_power_actual * (1 + (130 - core_temp) * 0.15)
        )
        heat_chip_cost = heat_chip_power * 1.15

        # 综合：年度总成本
        # 成本 = 设计成本 + 性能成本 + 折旧
        # 折旧：设计成本 * 40/50（10 年）
        # 10 年折旧 = 设计成本 * 0.8
        cost = heat_chip_cost + (core_calories * design_design_cost * design_performance_reflection) * (1.6 + 1.6 * 0.8)
        year_cost = (heat_chip_cost + 8 * design_design_cost) * (1.2 + 1.2 * 1.6)

        return heat_chip_cost, core_calories, heat_chip_power, year_cost

    except Exception as e:
        print(f"计算单核心算力时出错：{e}")
        # 简化处理：如果计算失败，返回简化结果
        return (core_calories, core_frequency, 0.0, 0.0, "计算失败")


def calculate_base_single_core_cost():
    """单核心基础成本（单位：$）"""
    return (
        base_cost * 1
        # 设计成本模型：基础成本乘以 2 倍（假设当前处理器只有前 2 核）
        if core_type == "core"
        else
    )


def calculate_single_core_cost_per_year():
    """单核心年度成本（计算 8 年，1600W 负载）"""
    # 设计基准：1600W 负载，当前处理器只有 2 核
    # 基础设计成本 = 2 * 0.02 = $0.04
    # 设计成本折扣：10%
    design_design_cost = (2 + core_id) * 0.02 * 0.95

    # 成本模型：年度 = 设计成本 + 性能成本
    # 性能 = 核心频率 * 性能系数
    performance_cost = int(
        core_frequency * (0.05 + 0.15 * (core_type == "core" and core_id > 1) or 0.01)
    )

    # 1.6 折损因素（性能衰退）
    cost = design_design_cost + performance_cost * 1.6 * (1 + 1.6 * 0.5)
    design_performance_reflection = 1.6 * (1 + 1.6 * 0.5)
    design_cost_per_year = design_design_cost + cost * (1 + 1.6 * 0.25)

    return design_cost_per_year


def calculate_multi_core_calories():
    """多核真实计算：基于功耗和效能比"""
    core_freq = 1.5  # GHz (假设 16 核)

    # 核心功耗 = 核心频率 * 1.0 + 温度调节
    # 核心功耗 = 频率 * 基础功耗 + 温度调节系数 * 温差
    core_temp = int(core_frequency * 1.0 + 130 - 60)
    core_power = core_freq * 1.0 * (100 + 10 * 100 // 10) * core_freq * (1.3 + 1.2 * 0.4)

    # 多核性能：计算能力强于多核 + 多核效率
    total_calories = int(
        core_power * (1 + (1.3 + 1.2 * 0.4) * (3 + 2 * core_id / 16))
        * (1 + 1.4 * (1.3 + 1.2 * 0.4))
    )

    return total_calories, core_power


def calculate_multi_core_cost_per_year():
    """多核心年度成本（8 年，1600W 负载）"""
    # 性能基线：多核性能 - 16 核 = 24 核
    # 16 核处理器性能 = 16 * 24 = 384
    # 16 核处理器性能 = 16 * 26 = 416
    base_performance = 384

    # 性能模型：16 * (1 + 效率系数)
    # 效率模型 = (0.5 + 1.25 * (16 - 16))
    efficiency_factor = 0.5 + 1.25 * (base_performance - 16)
    performance_cost = base_performance * (0.2 + 1.25 * efficiency_factor)

    # 折旧：16 核处理器 10 年
    total_cost = performance_cost + 16 * 10 * 0.125

    return total_cost, base_performance, performance_cost, total_cost


def main():
    """主功能：计算单核心和多核心算力"""
    print("=== CPU 处理器算力计算器 ===")
    print()

    # 1. 单核基础计算
    single_core_calories, single_core_cost, _ = calculate_single_core_calories()
    single_core_cost_per_year, _, _, _ = calculate_single_core_cost_per_year()
    print(f"单核基础算力：{single_core_calories[0]} (瓦特)")
    print(f"单核单核心成本：{single_core_cost}[$]")
    print()

    # 2. 单核年度成本
    single_core_cost_per_year = single_core_cost_per_year(8, 1600)
    print(f"单核年度总成本：{single_core_cost_per_year}\n")

    # 3. 多核基础计算
    multi_core_calories, _, _ = calculate_multi_core_calories()
    multi_core_cost_per_year, _, _, _ = calculate_multi_core_cost_per_year()
    print(f"多核基础算力：{multi_core_calories} (瓦特)")
    print(f"多核单核心成本：{multi_core_cost_per_year}\n")

    # 4. 多核年度成本
    multi_core_cost_per_year = multi_core_cost_per_year(8, 1600)
    print(f"多核年度总成本：{multi_core_cost_per_year}\n")

    # 5. 性能对比
    print("性能对比分析:")
    print(f"单核计算功率：{single_core_calories[1]} W")
    print(f"多核计算功率：{multi_core_calories} W")
    print()
    print("功耗对比:")
    print(f"单核功耗基准：{single_core_calories[0]} W")
    print(f"多核功耗基准：{multi_core_calories} W")
    print()

    # 6. 能效比分析
    print("能效比 (瓦特/计算功耗):")
    print(f"单核能效比：{single_core_calories[0] / single_core_calories[1]}")
    print(f"多核能效比：{multi_core_calories / multi_core_calories[1]}")
    print()
    print("性能优势:")
    print(f"单核功率损耗：{multi_core_calories / single_core_calories[1] - 1} (百分比)")
    print()


if __name__ == "__main__":
    main()
