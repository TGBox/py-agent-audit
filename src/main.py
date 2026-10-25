import sys
import tkinter as tk


def main() -> None:
    root = tk.Tk()
    root.title("py-agent-audit")
    root.geometry("800x600")
    label = tk.Label(root, text="Hallo aus py-agent-audit!", font=("Arial", 18))
    label.pack(expand=True)
    root.mainloop()

if __name__ == "__main__":
    main()