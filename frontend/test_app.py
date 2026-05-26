import streamlit as st
import subprocess
import threading
import queue
import os
import pandas as pd
import plotly.graph_objects as go

import time

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Test Station UI", layout="wide")   # Sets the page title and layout

# -----------------------------
# Session state initialization
# -----------------------------
if "process" not in st.session_state:
    st.session_state.process = None

if "log_queue" not in st.session_state:
    st.session_state.log_queue = queue.Queue()

if "log_text" not in st.session_state:
    st.session_state.log_text = ""

if "csv_tabs" not in st.session_state:
    # Each item: {"name": str, "data": DataFrame | None, "file_name": str | None}
    st.session_state.csv_tabs = []

if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = {"stop": False}

def stream_process_output(process, q, stop_flag):
    for line in iter(process.stdout.readline, ''):  # sentinel is empty string in text mode
        if stop_flag["stop"]:
            break
        q.put(line)
    process.stdout.close()

# -----------------------------
# Helper: launch test process
# -----------------------------
#def launch_test(test_id, serial_number, board_version, device_type, batch, csvs_to_write):
def launch_test(serial_number, board_version, device_type, batch, csvs_to_write):
    
    if st.session_state.process is not None:      # Checks if a process is already running
        st.warning("A test is already running.")
        return

    # Your main(argv, arc) consumes args positionally:
    # argv[1] = test_id
    # argv[2] = serial_number
    # argv[3] = board_version
    # argv[4-7] = extra (we'll use device_type, batch, and placeholders)
    cmd = [
        # sys.executable,
        "python",
        "-u",           # unbuffered output
        "../test.py",
        "1",
        serial_number if serial_number else "0",
        board_version if board_version else "0",
        device_type if device_type else "0",
        batch if batch else "0"
        # "0",
        # "0",
    ]

    # Pass CSV list via environment variable
    env = os.environ.copy()
    env["CSV_LIST"] = ",".join(csvs_to_write) if csvs_to_write else ""
    #env["PYTHONUNBUFFERED"] = "1"  # belt-and-suspenders; Removed for now

    st.session_state.stop_flag["stop"] = False
    st.session_state.log_text = ""

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,           # return str, not bytes
        env=env,
    )

    st.session_state.process = process

    reader = threading.Thread(
        target=stream_process_output,
        args=(process, st.session_state.log_queue, st.session_state.stop_flag),
        daemon=True,
    )
    reader.start()

    def watch_and_finalize(proc, stop_flag):
        rc = proc.wait() # Wait for test.py process to complete
        # Signal the UI and stop the reader loop if it’s still running
        stop_flag["stop"] = True
        # Push a final line to the queue so the UI shows completion
        st.session_state.log_queue.put(f"\nTest process exited with code {rc}.\n")
        # Marks process as no longer running
        st.session_state.process = None

    
    watcher = threading.Thread(
        target=watch_and_finalize,
        args=(process, st.session_state.stop_flag),
        daemon=True,
    )
    watcher.start()


# -----------------------------
# Helper: stop test process
# -----------------------------
# def stop_test():
#     if st.session_state.process is not None:
#         #st.session_state.stop_requested = True # REPLACED
#         st.session_state.stop_flag["stop"] = True # REPLACEMENT
#         try:
#             st.session_state.process.terminate()
#         except Exception:
#             pass
#         st.session_state.process = None

def stop_test():
    proc = st.session_state.process
    if proc is not None:
        st.session_state.stop_flag["stop"] = True
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)  # give it a moment to exit gracefully
            except subprocess.TimeoutExpired:
                proc.kill()           # force kill if needed
        except Exception:
            pass
        finally:
            st.session_state.process = None

# ============================================================
# Sidebar – Test parameters + CSV output selection
# ============================================================
st.sidebar.header("Test parameters")

# Theme toggle at the top
st.sidebar.markdown("---")

# test_id = st.sidebar.text_input("Test ID")
serial_number = st.sidebar.text_input("Serial Number")
board_version = st.sidebar.text_input("Board Version")
device_type = st.sidebar.text_input("Device Type")
batch = st.sidebar.text_input("Batch")

st.sidebar.markdown("---")
st.sidebar.subheader("CSV files to write results to")

# csv_list_input = st.sidebar.text_area(
#     "CSV filenames (one per line)",
#     help=(
#         "These names are passed to test.py via the CSV_LIST env var.\n"
#         "Your script will write Pass/Fail results into these files."
#     ),
# )
# csvs_to_write = [line.strip() for line in csv_list_input.splitlines() if line.strip()]

st.sidebar.subheader("Select CSVs to write results to")

# Build list of CSV filenames from tabs
available_csvs = [
    tab["file_name"]
    for tab in st.session_state.csv_tabs
    if tab["file_name"] is not None
]

if available_csvs:
    csvs_to_write = st.sidebar.multiselect(
        "Choose CSVs",
        options=available_csvs,
        default=[],
    )
else:
    st.sidebar.info("Upload CSVs in tabs to enable selection.")
    csvs_to_write = []

start_button = st.sidebar.button("Start Test")
stop_button = st.sidebar.button("Stop Test")

if start_button:
    launch_test(
        # test_id=test_id,
        serial_number=serial_number,
        board_version=board_version,
        device_type=device_type,
        batch=batch,
        csvs_to_write=csvs_to_write,
    )

if stop_button:
    stop_test()


# ============================================================
# Layout – top region (CSV/FPY + console)
# ============================================================
col1, col2 = st.columns([2, 1])

# -----------------------------
# LEFT: CSV viewer + FPY
# -----------------------------
with col1:
    st.header("CSV viewer & First Pass Yield")

    if st.button("Add CSV Tab"):
        idx = len(st.session_state.csv_tabs) + 1
        st.session_state.csv_tabs.append(
            {"name": f"CSV Tab {idx}", "data": None, "file_name": None}
        )

    if not st.session_state.csv_tabs:
        st.info("No CSV tabs yet. Click 'Add CSV Tab' to start.")
    else:
        tab_labels = [tab["name"] for tab in st.session_state.csv_tabs]
        tabs = st.tabs(tab_labels)

        for i, tab in enumerate(tabs):
            with tab:
                # Tab name
                new_name = st.text_input(
                    "Tab name",
                    value=st.session_state.csv_tabs[i]["name"],
                    key=f"tab_name_{i}",
                )
                # Close tab button
                if st.button("Close Tab", key=f"close_tab_{i}"):
                  st.session_state.csv_tabs.pop(i)
                  st.rerun()
                st.session_state.csv_tabs[i]["name"] = new_name

                # Upload a CSV for this tab
                uploaded_file = st.file_uploader(
                    "Upload FPY/CSV file for this tab",
                    type=["csv"],
                    key=f"csv_uploader_{i}",
                )

                if uploaded_file is not None:
                    try:
                        df = pd.read_csv(uploaded_file)
                        st.session_state.csv_tabs[i]["data"] = df
                        st.session_state.csv_tabs[i]["file_name"] = uploaded_file.name
                    except Exception as e:
                        st.error(f"Error reading CSV: {e}")

                df = st.session_state.csv_tabs[i]["data"]

                if df is not None:
                    st.subheader("Raw data")
                    st.dataframe(df, width='stretch')

                    st.markdown("---")
                    st.subheader("First Pass Yield (FPY) analysis")

                    if df.empty:
                        st.warning("CSV is empty; cannot compute FPY.")
                    else:
                        # Your FPY CSV format:
                        # Device Type,Rev,Serial,MAC,Status,Date
                        columns = list(df.columns)

                        # Try to auto-detect based on your schema, but allow override
                        # result_col = "Status" if "Status" in columns else columns[0]
                        # time_col = "Date" if "Date" in columns else "<None>"
                        result_col = "Status" if "Status" in columns else st.selectbox(
                                label="Result/status column (Pass/Fail)",
                                options=["<None>"] + columns,
                                index=(["<None>"] + columns).index("Result")
                                if "Result" in columns
                                else 0,
                                key=f"result_col_{i}",
                            )
                        if "Date" in columns:
                            time_col = "Date" 
                        else:
                            time_col = st.selectbox(
                                label="Time column for FPY over time (optional)",
                                options=["<None>"] + columns, 
                                index=(["<None>"] + columns).index("Time")
                                if "Time" in columns
                                else 0,
                                key=f"time_col_{i}",
                            )

                        pass_value = "Pass"

                        # Overall FPY
                        total = len(df)
                        passes = (df[result_col].astype(str) == pass_value).sum()
                        fpy = passes / total if total > 0 else 0

                        st.write(f"**Total units:** {total}")
                        st.write(f"**Passes:** {passes}")
                        st.write(f"**Fails:** {total - passes}")
                        st.write(f"**FPY:** {fpy * 100:.2f}%")

                        # -------------------------
                        # FPY bar chart (Pass vs Fail)
                        # -------------------------
                        bar_df = pd.DataFrame(
                            {
                                "Result": ["Pass", "Fail"],
                                "Count": [passes, total - passes],
                            }
                        ).set_index("Result")

                        st.markdown("**FPY bar chart (Pass vs Fail)**")
                        st.bar_chart(bar_df, width='stretch')

                        # -------------------------
                        # FPY line chart over time (cumulative)
                        # -------------------------
                        if time_col != "<None>":
                            time_df = df.copy()

                            # Parse dates
                            time_df[time_col] = pd.to_datetime(
                                time_df[time_col], errors="coerce"
                            )
                            time_df = time_df.dropna(subset=[time_col])

                            if time_df.empty:
                                st.warning(
                                    "After parsing the time column, no valid timestamps remain."
                                )
                            else:
                                time_df = time_df.sort_values(by=time_col)

                                # Mark pass/fail as 1/0
                                time_df["is_pass"] = (
                                    time_df[result_col].astype(str) == pass_value
                                ).astype(int)

                                # Cumulative counts
                                time_df["cumulative_total"] = range(1, len(time_df) + 1)
                                time_df["cumulative_pass"] = time_df["is_pass"].cumsum()
                                time_df["FPY"] = (
                                    time_df["cumulative_pass"] / time_df["cumulative_total"]
                                )

                                line_chart_df = time_df.set_index(time_col)[["FPY"]]

                                st.markdown("**FPY line chart over time (cumulative)**")
                                
                                # Create Plotly figure
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=line_chart_df.index,
                                    y=line_chart_df["FPY"],
                                    mode='lines',
                                    name='FPY',
                                    line=dict(width=2)
                                ))
                                fig.update_layout(
                                    xaxis_title=time_col,
                                    yaxis_title="FPY",
                                    yaxis=dict(range=[0, 1], tickformat='.2%'),
                                    hovermode='x unified',
                                    height=400,
                                    showlegend=False
                                )
                                
                                # st.plotly_chart(fig, width='content')
                                st.plotly_chart(fig, width='stretch')
                        else:
                            st.info(
                                "Select a time column (e.g., 'Date') to see FPY as a line chart over time."
                            )
                else:
                    st.info("Upload a CSV to see data and FPY analysis in this tab.")


# -----------------------------
# RIGHT: live console output
# -----------------------------

with col2:
    st.header("Test console output")

    # Pull log lines from the queue
    while not st.session_state.log_queue.empty():
        st.session_state.log_text += st.session_state.log_queue.get()

    st.text_area(
        "Console log",
        value=st.session_state.log_text,
        height=500,
    )

    # if st.session_state.process is not None:
    #     st.success("Test is running.")
    #     time.sleep(0.1) 
    #     st.rerun() # Force UI refresh so logs update live
    
    proc = st.session_state.process
    if proc is not None:
        rc = proc.poll()  # None -> still running; integer -> finished
        if rc is None:
            st.success("Test is running.")
            time.sleep(0.1)
            st.rerun()  # keep refreshing *only while running*
        else:
            # Process finished; clean up state (watcher will also set these)
            st.session_state.process = None
            st.session_state.stop_flag["stop"] = True
            st.success(f"Test finished with exit code {rc}.")
    else:
        st.info("No test is currently running.")