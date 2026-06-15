import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

def prompt(title_text = "Title Header", message_text = "Message Body"):
    root = tk.Tk()

    # Make the root window invisible
    root.withdraw()

    # Force it to be the topmost window
    root.attributes('-topmost', True)
    root.lift()
    root.focus_force()

    # # Show the popup
    # result = messagebox.askyesno(
    #     title=title_text,
    #     message=message_text,
    #     parent=root
    # )

    # Show the popup
    result = messagebox.askokcancel(
        title=title_text,
        message=message_text,
        parent=root
    )

    root.destroy()
    return result

def abort_retry_ignore_prompt(title: str = "Abort, Retry, Ignore", message: str = "Message Body") -> str:
    root = tk.Tk()

    # Make the root window invisible
    root.withdraw()

    # Force it to be the topmost window
    root.attributes('-topmost', True)
    root.lift()
    root.focus_force()

    s = messagebox._show(title, message, messagebox.QUESTION, messagebox.ABORTRETRYIGNORE)
    s = str(s)
    if s == messagebox.ABORT: result = "abort"
    elif s == messagebox.RETRY: result = "retry"
    elif s == messagebox.IGNORE: result = "ignore"
    else: 
        print("Result is unexpected value:", s)
        result = None
    return result

def multi_selection_prompt(
    title: str,
    message: str,
    selections: list[str]
    ) -> dict:
    root = tk.Tk()
    root.withdraw()

    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.attributes("-topmost", True)
    dialog.grab_set()  # modal

    result = {
        "action": None,
        "selected": []
    }

    # ---- Message ----
    ttk.Label(dialog, text=message, wraplength=400).pack(
        padx=20, pady=(15, 10)
    )

    # ---- Checkbox list ----
    vars_by_selection = {}
    frame = ttk.Frame(dialog)
    frame.pack(padx=20, pady=10, fill="x")

    for selection in selections:
        var = tk.BooleanVar(value=True)
        vars_by_selection[selection] = var
        cb: ttk.Checkbutton = ttk.Checkbutton(
            frame,
            text=selection,
            variable=var,
            onvalue=True,
            offvalue=False, 
            tristatevalue=None
        )
        cb.pack(anchor="w")
        
        # cb.state(["selected"])    # ensure checked NOTE Idk if needed, because onvalue=True should do this already
        cb.state(["!alternate"])    # remove dash state

    # ---- Button handlers ----
    def collect_selection():
        result["selected"] = [
            selection for selection, var in vars_by_selection.items() if var.get()
        ]

    def yes():
        collect_selection()
        result["action"] = "yes"
        dialog.destroy()

    def yes_to_all():
        collect_selection()
        result["action"] = "yes_to_all"
        result["selected"] = selections
        dialog.destroy()

    def no():
        result["action"] = "no"
        dialog.destroy()

    # ---- Buttons ----
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(pady=15)

    ttk.Button(btn_frame, text="Yes to All", command=yes_to_all).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Yes to Selected", command=yes).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="No to All", command=no).pack(side="left", padx=5)

    dialog.wait_window()
    root.destroy()
    return result["selected"]

if __name__ == "__main__":
    response = multi_selection_prompt(
        title="Add Device to CSVs",
        message="Select which CSV files this device should be added to:",
        selections=[
            "first_pass_yield_batch_1234.csv",
            "first_pass_yield_batch_CCUV_2025.csv",
            "first_pass_yield_batch_ALL_2025.csv",
            "batch_1234.csv",
            "25_12_22.csv"
        ]
    )

    print(response)
