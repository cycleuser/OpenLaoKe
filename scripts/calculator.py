import tkinter as tk
from tkinter import messagebox, ttk


class Calculator:
    def __init__(self, root):
        self.root = root
        self.create_widgets()

    def create_widgets(self):
        # 创建主窗口
        self.root.title("计算器")
        self.root.geometry("320x450")
        self.root.resizable(True, True)

        # 顶部标题栏
        tk.Label(self.root, text="计算器", font=("Arial", 16, "bold")).pack(pady=10)

        # 输入区域
        self.entry_label = ttk.Label(
            self.root,
            text="( )",
            fg="#333",
            padding=20
        ).pack(pady=(0, 5))

        # 创建输入框组
        input_row = ttk.Frame(self.entry_label)
        input_row.pack(pady=(5, 10), expand=True, fill="x")

        self.number_entry = tk.Entry(
            input_row,
            font=("Arial", "24"),
            width=6,
            background="#333" if hasattr(self.root, 'bg') else "#f5f5f5"
        ).pack(side=tk.LEFT, fill="x", padx=(10, 0), pady=(0, 10))

        def calculate():
            """计算当前输入"""
            try:
                result = self.calculate_value()
                tk.Label(
                    self.root,
                    text=f"结果: {result}",
                    font=("Arial", "24"),
                    fg="white" if not isinstance(result, bool) else "#00ff00",
                    padding=10
                ).pack(pady=(50, 20))
                self.refresh()
            except ValueError as e:
                messagebox.showerror("错误", str(e))

        # 添加计算按钮
        tk.Button(
            self.root,
            text="= ",
            font=("Arial", "16"),
            command=calculate,
            bg="#4CAF50" if hasattr(self.root, 'bg') else "#28a745"
        ).pack(pady=(30, 10))

    def calculate_value(self):
        """计算当前输入的值"""
        return float(self.number_entry.get().strip())

    def refresh(self):
        """刷新按钮显示"""
        self.number_entry.delete(0, tk.END)
        if self.entry_label.text == "结果:":
            self.entry_label.insert(tk.END, f"结果：{self.number_entry.get()}")
        else:
            self.entry_label.insert(tk.END, "( )")

    def run(self):
        """运行计算器"""
        result = tk.Label(
            self.root,
            text="输入运算结果",
            font=("Arial", "16"),
            padding=20,
            fg="#333" if hasattr(self.root, 'bg') else "#f5f5f5"
        ).pack(pady=(0, 25))

        def run_input():
            try:
                result = float(self.number_entry.get().strip())
                self.refresh()
            except ValueError as e:
                messagebox.showerror("错误", str(e))

        tk.Button(
            result.root,
            text="按",
            font=("Arial", "12"),
            command=run_input,
            bg="#4CAF50" if hasattr(self.root, 'bg') else "#28a745"
        ).pack(pady=(30, 15))

    def start_new_calc(self):
        """运行新的计算器"""
        self.refresh()


def main():
    root = tk.Tk()
    app = Calculator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
