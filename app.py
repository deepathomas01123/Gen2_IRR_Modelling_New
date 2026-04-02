import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.cache_data.clear()
st.set_page_config(
    layout="wide"
)
# ============================================================
# PAGE CONFIG
# ============================================================
tab_results, tab_dictionary = st.tabs(
    ["📊 Harvest Results", "📘 Data Dictionary"]
)

with tab_results:

    st.title("🌱 GEN2 IRR Modelling")

    # ============================================================
    # LOAD SALES BUDGET (NUMERIC FISCAL YEAR)
    # ============================================================
    @st.cache_data
    def load_sales_budget():
        FILE_PATH = "data/SalesBudget.xlsx"
        df = pd.read_excel(FILE_PATH, header=0)

        df.columns = (
            df.columns.astype(str)
            .str.replace("\xa0", " ", regex=False)
            .str.replace("\n", " ", regex=False)
            .str.strip()
        )

        df["Fiscal Week No"] = (
            df["Week"]
            .astype(str)
            .str.extract(r"(\d+)", expand=False)
            .astype(int)
        )

        df["Budget Sales Price($)"] = (
            df["BX Budget Return (Kg)"]
            .astype(str)
            .str.replace(r"[^\d.]", "", regex=True)
            .astype(float)
        )

        df["Fiscal Year"] = (
            df["CY"]
            .astype(str)
            .str.replace("CY", "")
            .astype(int)
            + 2000
        )

        return df[
            ["Fiscal Year", "Fiscal Week No", "Budget Sales Price($)"]
        ].dropna()


    budget_lookup = load_sales_budget()

    # ============================================================
    # PROCESS HARVEST DATA
    # ============================================================
    df = pd.read_excel("data/Actuals_.xlsx")
    df.columns = df.columns.str.strip()
    st.success("Harvest file uploaded successfully!")

    required_columns = [
        "Costa Fiscal Year",
        "Pick Date",
        "Fiscal Week No",
        "Plant",
        "Product Variety",
        "Yield Kg",
        "Variety Area (ha)",
        "Cost Per Kg - Total Harvest Cost"
    ]

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        st.error(f"Missing columns: {missing}")
        st.stop()

    df["Fiscal Year"] = (
        df["Costa Fiscal Year"]
        .astype(str)
        .str.extract(r"(\d{4})", expand=False)
        .astype(int)
    )

    df["Fiscal Week No"] = df["Fiscal Week No"].astype(int)
    df["Pick Date"] = pd.to_datetime(df["Pick Date"], dayfirst=False).dt.date

    # ============================================================
    # SIDEBAR INPUTS
    # ============================================================
    st.sidebar.header("🔧 Harvest Inputs")

    st.sidebar.subheader("📦 Harvest Speed Configuration")

    if "minutes_per_100m" not in st.session_state:
        st.session_state.minutes_per_100m = 8.5

    if "time_per_cycle" not in st.session_state:
        st.session_state.time_per_cycle = st.session_state.minutes_per_100m * 60 / 33

    def update_time_per_cycle():
        st.session_state.time_per_cycle = (
            st.session_state.minutes_per_100m * 60 / 33
        )

    def update_minutes_per_100m():
        st.session_state.minutes_per_100m = (
            st.session_state.time_per_cycle * 33 / 60
        )

    with st.sidebar.container():

        st.number_input(
            "Harvest speed (minutes / 100m)",
            key="minutes_per_100m",
            step=0.1,
            on_change=update_time_per_cycle
        )

        st.number_input(
            "Time per cycle (sec / cycle)",
            key="time_per_cycle",
            step=0.1,
            on_change=update_minutes_per_100m
        )

        harvest_speed = (
            (100 * 8.5 / 3)
            / (st.session_state.minutes_per_100m / 60)
            / 10000
        )

        st.markdown(
            f"""
            **Calculated Harvest Speed:**  
            🌱 `{harvest_speed:.4f} Ha / Hour`
            """
        )

    num_machines = st.sidebar.number_input(
        "Number of Machines",
        value=10,
        step=1
    )

    session_length = st.sidebar.number_input(
        "Session Length (Hours)",
        value=8.0,
        min_value=0.5,
        max_value=24.0,
        step=0.5
    )
    if session_length >= 24.0:
        st.sidebar.warning("⚠️ Session length is at the maximum of 24 hours.")

    lost_damaged_pct = st.sidebar.number_input(
        "Lost / Damaged %",
        value=15.0,
        step=1.0
    ) / 100

    machine_to_staff = st.sidebar.number_input(
        "Machine to Staff Ratio",
        value=5.0,
        step=1.0
    )

    staff_wages = st.sidebar.number_input(
        "Staff Wages ($/hr)",
        value=32.0,
        step=1.0
    )

    max_available_hours = num_machines * session_length

    seconds_efficiency = st.sidebar.number_input(
        "Seconds Efficiency (%)",
        value=90.0,
        step=1.0
    ) / 100

    packaging_cost_per_kg = st.sidebar.number_input(
        "Packaging Cost ($/kg)",
        value=4.0,
        step=0.5
    )

    overhead_pct = st.sidebar.number_input(
        "Overhead Cost (%)",
        value=19.0,
        step=1.0
    ) / 100

    # ============================================================
    # FILTERS (TIME → PLANT → VARIETY)
    # ============================================================
    st.sidebar.subheader("📅 Time Filters")
    selected_fy = 2025

    st.sidebar.selectbox(
        "Fiscal Year",
        options=[2025],
        index=0,
        disabled=True
    )

    df_time = df[df["Fiscal Year"] == 2025]

    fw_list = sorted(df_time["Fiscal Week No"].unique())
    selected_fw = st.sidebar.multiselect(
        "Fiscal Week",
        options=fw_list,
        default=fw_list
    )

    df_time = df_time[df_time["Fiscal Week No"].isin(selected_fw)]

    if not selected_fw or df_time.empty:
        st.info("👆 Please select at least one **Fiscal Week** to continue.")
        st.stop()

    st.sidebar.subheader("🌱 Plant Filter")
    plant_list = sorted(df_time["Plant"].dropna().unique())
    selected_plants = st.sidebar.multiselect(
        "Plant",
        options=plant_list,
        default=plant_list[:1] if plant_list else []
    )

    df_plant = df_time[df_time["Plant"].isin(selected_plants)]

    if not selected_plants or df_plant.empty:
        st.info("👆 Please select at least one **Plant** to continue.")
        st.stop()

    st.sidebar.subheader("🌿 Variety Filter")
    variety_list = sorted(df_plant["Product Variety"].dropna().unique())

    variety_options = ["Select All"] + variety_list

    selected_varieties = st.sidebar.multiselect(
        "Variety",
        options=variety_options,
        default=["Select All"]
    )

    if "Select All" in selected_varieties:
        selected_varieties = variety_list

    if not selected_varieties:
        st.info("👆 Please select at least one **Variety** to continue.")
        st.stop()

    filtered_df = df_plant[
        df_plant["Product Variety"].isin(selected_varieties)
    ].copy()

    if filtered_df.empty:
        st.info("👆 No data matches the current filter selection. Please adjust your filters.")
        st.stop()

    # ============================================================
    # MERGE BUDGET
    # ============================================================
    filtered_df = filtered_df.merge(
        budget_lookup,
        on=["Fiscal Year", "Fiscal Week No"],
        how="left"
    )

    if filtered_df["Budget Sales Price($)"].isna().any():
        st.warning("⚠️ Some Fiscal Year / Week combinations missing budget mapping")

    # ============================================================
    # PRE-CALCULATE Yield/Ha at VARIETY level (not location level)
    # This avoids distortion from uneven yield distribution across locations
    # ============================================================
    variety_totals = (
        filtered_df
        .groupby(["Plant", "Product Variety", "Pick Date"])
        .agg(
            Total_Yield_Kg=("Yield Kg", "sum"),
            Total_Area_Ha=("Variety Area (ha)", "sum"),
            # Weighted average cost per kg — weighted by yield kg
            Weighted_Cost=("Cost Per Kg - Total Harvest Cost", lambda x: 
                (x * filtered_df.loc[x.index, "Yield Kg"]).sum() / 
                filtered_df.loc[x.index, "Yield Kg"].sum()
                if filtered_df.loc[x.index, "Yield Kg"].sum() > 0 else 0
            )
        )
        .reset_index()
    )
    variety_totals["Yield/Ha"] = variety_totals["Total_Yield_Kg"] / variety_totals["Total_Area_Ha"]
    
    filtered_df = filtered_df.merge(
        variety_totals[["Plant", "Product Variety", "Pick Date", "Yield/Ha", "Weighted_Cost"]],
        on=["Plant", "Product Variety", "Pick Date"],
        how="left"
    )
    
    # Replace Cost Per Kg with the variety-level weighted average
    filtered_df["Cost Per Kg - Total Harvest Cost"] = filtered_df["Weighted_Cost"]

    filtered_df["Cost/Ha"] = (
        filtered_df["Cost Per Kg - Total Harvest Cost"] * filtered_df["Yield/Ha"]
    )

    # ============================================================
    # ALLOCATION LOGIC
    # Daily capacity (ha) = num_machines × session_length × harvest_speed
    # Varieties sorted by highest Cost/Ha get priority each day per plant.
    # One capacity pool per Plant per day — shared across all locations.
    # ============================================================
    daily_capacity_ha = num_machines * session_length * harvest_speed

    filtered_df = filtered_df.sort_values(
        ["Pick Date", "Plant", "Cost/Ha"],
        ascending=[True, True, False]
    ).copy()

    filtered_df["Area_Harvested"] = 0.0

    for (pick_date, plant), group in filtered_df.groupby(["Pick Date", "Plant"]):

        remaining_capacity = daily_capacity_ha

        for idx in group.index:
            variety_area = filtered_df.loc[idx, "Variety Area (ha)"]

            if remaining_capacity <= 0:
                area = 0
            elif remaining_capacity >= variety_area:
                area = variety_area
            else:
                area = remaining_capacity

            filtered_df.loc[idx, "Area_Harvested"] = area
            remaining_capacity -= area

    filtered_df = filtered_df.reset_index(drop=True).copy()

    # ============================================================
    # YIELD HARVESTED & YIELD LOST
    # ============================================================
    filtered_df["Yield_Lost"] = (
        lost_damaged_pct
        * filtered_df["Area_Harvested"]
        * filtered_df["Yield/Ha"]
    )

    filtered_df["Yield_Harvested"] = (
        (1 - lost_damaged_pct)
        * filtered_df["Area_Harvested"]
        * filtered_df["Yield/Ha"]
    )

    # ============================================================
    # HARVEST STATUS
    # ============================================================
    filtered_df["Harvest Status"] = np.select(
        [
            filtered_df["Area_Harvested"] == 0,
            filtered_df["Area_Harvested"] < filtered_df["Variety Area (ha)"],
            filtered_df["Area_Harvested"] >= filtered_df["Variety Area (ha)"]
        ],
        ["Not Harvested", "Partially Harvested", "Fully Harvested"],
        default="Unknown"
    )

    # ============================================================
    # PLATFORM RUN TIME
    # ============================================================
    filtered_df["Combined Platform Run time"] = (
        filtered_df["Area_Harvested"] / harvest_speed
    )

    # ============================================================
    # OPPORTUNITY COST & SAVINGS
    # ============================================================
    filtered_df["Opportunity Cost"] = (
        filtered_df["Budget Sales Price($)"] * filtered_df["Yield_Lost"] * seconds_efficiency
        - (
            overhead_pct * filtered_df["Cost Per Kg - Total Harvest Cost"] * filtered_df["Yield_Lost"]
            + packaging_cost_per_kg * filtered_df["Yield_Lost"] * seconds_efficiency
        )
    ).clip(lower=0)

    filtered_df["Platform Kg/hour"] = np.where(
        filtered_df["Combined Platform Run time"] > 0,
        filtered_df["Yield_Harvested"] / filtered_df["Combined Platform Run time"],
        np.nan
    )

    labour_cost_per_machine = staff_wages / machine_to_staff

    filtered_df["Platform cost/kg"] = np.where(
        (filtered_df["Platform Kg/hour"] > 0) & (~np.isnan(filtered_df["Platform Kg/hour"])),
        labour_cost_per_machine / filtered_df["Platform Kg/hour"],
        0.0
    )

    filtered_df["Daily harvest savings"] = (
        filtered_df["Yield_Harvested"]
        * (
            filtered_df["Cost Per Kg - Total Harvest Cost"]
            - filtered_df["Platform cost/kg"]
        )
    ).clip(lower=0)

    filtered_df["Savings - Yield loss cost"] = (
        filtered_df["Daily harvest savings"]
        - filtered_df["Opportunity Cost"]
    )

    # ============================================================
    # ROW HIGHLIGHTING
    # ============================================================
    def highlight_rows(row):
        if row["Harvest Status"] == "Fully Harvested":
            return ["background-color: #d4edda"] * len(row)
        elif row["Harvest Status"] == "Partially Harvested":
            return ["background-color: #fff3cd"] * len(row)
        elif row["Harvest Status"] == "Not Harvested":
            return ["background-color: #f8d7da"] * len(row)
        else:
            return [""] * len(row)

    st.subheader("📊 Harvest Results")
    cols_to_hide = ["Fiscal Year", "Fiscal Week No", "Costa Fiscal Year"]
    display_results = filtered_df.drop(
        columns=[c for c in cols_to_hide if c in filtered_df.columns]
    )
    styled_results = display_results.style.apply(highlight_rows, axis=1)
    st.dataframe(styled_results, use_container_width=True)

    st.markdown(
        """
        **Harvest Allocation Legend**
        
        🟢 Green → Fully Harvested  
        🟡 Yellow → Partially Harvested  
        🔴 Red → Not Harvested (platform capacity exhausted)
        """
    )

    # Force structure reset
    filtered_df = pd.DataFrame(filtered_df)
    filtered_df.columns = filtered_df.columns.astype(str).str.strip()

    # ============================================================
    # SUMMARY + TOTAL ROW
    # ============================================================
    grouped_summary = (
        filtered_df
        .groupby(["Plant", "Product Variety"], as_index=False)
        .agg(
            Yield_Kg=("Yield Kg", "sum"),
            Area_Harvested=("Area_Harvested", "sum"),
            Yield_Harvested=("Yield_Harvested", "sum"),
            Yield_Lost=("Yield_Lost", "sum"),
            Daily_harvest_savings=("Daily harvest savings", "sum"),
            Savings_Yield_loss_cost=(
                "Savings - Yield loss cost",
                lambda x: x[x > 0].sum()
            )
        )
    )

    total_row = pd.DataFrame({
        "Plant": ["TOTAL"],
        "Product Variety": [""],
        "Yield_Kg": [grouped_summary["Yield_Kg"].sum()],
        "Area_Harvested": [grouped_summary["Area_Harvested"].sum()],
        "Yield_Harvested": [grouped_summary["Yield_Harvested"].sum()],
        "Yield_Lost": [grouped_summary["Yield_Lost"].sum()],
        "Daily_harvest_savings": [grouped_summary["Daily_harvest_savings"].sum()],
        "Savings_Yield_loss_cost": [grouped_summary["Savings_Yield_loss_cost"].sum()]
    })

    grouped_summary = pd.concat(
        [grouped_summary, total_row],
        ignore_index=True
    )

    plant_savings = (
        filtered_df
        .groupby("Plant", as_index=False)
        .agg(Net_Savings=("Savings - Yield loss cost", "sum"))
        .sort_values("Net_Savings", ascending=False)
    )

    daily_savings = (
        filtered_df
        .groupby(["Pick Date", "Plant"], as_index=False)
        .agg(Net_Savings=("Savings - Yield loss cost", "sum"))
    )

    plant_variety_savings = (
        filtered_df
        .groupby(["Plant", "Product Variety"], as_index=False)
        .agg(Net_Savings=("Savings - Yield loss cost", "sum"))
    )

    stacked_df = (
        plant_variety_savings
        .pivot(index="Plant", columns="Product Variety", values="Net_Savings")
        .fillna(0)
    )

    display_df = grouped_summary.rename(columns={
        "Area_Harvested": "Area Harvested (Ha)",
        "Yield_Harvested": "Yield Harvested (Kg)",
        "Yield_Lost": "Yield Lost (Kg)",
        "Daily_harvest_savings": "Daily Harvest Savings ($)",
        "Savings_Yield_loss_cost": "Net Savings ($)"
    })

    styled_df = display_df.style.format({
        "Area Harvested (Ha)": "{:,.2f}",
        "Yield Harvested (Kg)": "{:,.2f}",
        "Yield Lost (Kg)": "{:,.2f}",
        "Daily Harvest Savings ($)": "${:,.2f}",
        "Net Savings ($)": "${:,.2f}",
    })

    st.subheader("📊 Combined Summary (Grouped)")
    st.dataframe(styled_df, use_container_width=True)

    total_days = filtered_df.shape[0]
    positive_days = (filtered_df["Savings - Yield loss cost"] > 0).sum()

    pct_positive_days = (
        positive_days / total_days * 100
        if total_days > 0 else 0
    )

    st.metric(
        label="📈 % Days with Positive Net Savings",
        value=f"{pct_positive_days:.1f}%",
        help="Percentage of harvest days where Savings - Yield loss cost was greater than zero"
    )

    st.subheader("📈 Daily Net Savings Trend by Plant")

    daily_savings["Pick Date"] = pd.to_datetime(daily_savings["Pick Date"])

    line_chart = (
        alt.Chart(daily_savings)
        .mark_line(point=True)
        .encode(
            x=alt.X("Pick Date:T", title="Pick Date"),
            y=alt.Y(
                "Net_Savings:Q",
                title="Net Savings ($)",
                axis=alt.Axis(format="$,.2f")
            ),
            color=alt.Color("Plant:N", title="Plant"),
            tooltip=[
                alt.Tooltip("Pick Date:T", title="Date"),
                alt.Tooltip("Plant:N", title="Plant"),
                alt.Tooltip("Net_Savings:Q", title="Net Savings ($)", format="$,.2f")
            ]
        )
        .properties(height=400)
    )

    st.altair_chart(line_chart, use_container_width=True)

    st.subheader("📊 Net Savings by Plant & Variety (Selected Year)")

    st.bar_chart(
        stacked_df,
        width="stretch"
    )

    # ============================================================
    # MACHINE INVESTMENT
    # ============================================================
    st.markdown("---")
    st.subheader("💰 Machine Investment")

    col_m1, col_m2 = st.columns(2)

    machine_cost = col_m1.number_input(
        "Machine Cost",
        value=250000,
        step=2000
    )

    col_m2.markdown(
        f"""
        <div style="
            padding:15px;
            background-color:#f5f5f5;
            border-radius:10px;
            text-align:center;
        ">
            <div style="font-size:16px; color:gray;">No. of Machines</div>
            <div style="font-size:36px; font-weight:bold;">{num_machines}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    total_spend = machine_cost * num_machines

    st.markdown(
        f"**Total Investment:**  \n"
        f"💲 `{total_spend:,.0f}`"
    )

    # ============================================================
    # INVESTMENT SUMMARY
    # ============================================================
    st.markdown("## 💰 Investment Summary")

    total_savings_year = grouped_summary.loc[
        grouped_summary["Plant"] == "TOTAL",
        "Savings_Yield_loss_cost"
    ].values[0]

    # ============================================================
    # CURRENT FOOTPRINT — raw df, plant filter only
    # ============================================================
    df_plant_raw = df[
        (df["Fiscal Year"] == 2025) &
        (df["Plant"].isin(selected_plants))
    ]

    step1 = (
        df_plant_raw
        .groupby(["Plant", "Location", "Product Variety",
                  "Pick Event Number", "Pick Event: First Pick Date"])["Variety Area (ha)"]
        .mean()
        .reset_index()
    )

    step2 = (
        step1
        .groupby(["Plant", "Location", "Product Variety"])["Variety Area (ha)"]
        .max()
        .reset_index()
    )

    current_footprint = step2["Variety Area (ha)"].sum()

    st.markdown("### 📈 Growth Assumptions")

    col_f1, col_f2 = st.columns(2)

    footprint_expansion = col_f1.number_input(
        "Footprint (Total Ha)",
        value=float(current_footprint),
        step=1.0
    )

    cpi_pct = col_f2.number_input(
        "CPI Increase (%)",
        value=0.0,
        step=0.5
    ) / 100

    projection_years = st.slider(
        "Projection Period (Years)",
        min_value=1,
        max_value=10,
        value=1
    )

    total_spend = machine_cost * num_machines

    footprint_factor = (
        footprint_expansion / current_footprint
        if current_footprint > 0 else 1
    )

    adjusted_annual_savings = total_savings_year * footprint_factor * (1 + cpi_pct)

    net_position_selected_year = (
        adjusted_annual_savings * projection_years
    ) - total_spend

    if adjusted_annual_savings > 0:
        payback_period_years = total_spend / adjusted_annual_savings
    else:
        payback_period_years = 0

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Machine Investment",
        f"${total_spend:,.0f}"
    )

    col2.metric(
        "Total Annual Savings",
        f"${adjusted_annual_savings:,.0f}"
    )

    col3.metric(
        f"Net Position After {projection_years} Years",
        f"${net_position_selected_year:,.0f}"
    )

    col4.metric(
        "Payback Period",
        f"{payback_period_years:.2f} yrs"
    )

    # ============================================================
    # MULTI-YEAR PROJECTION CHART
    # ============================================================
    years = list(range(0, 11))

    cumulative_position = []

    for year in years:
        if year == 0:
            cumulative_position.append(-total_spend)
        else:
            cumulative_position.append(
                -total_spend + (adjusted_annual_savings * year)
            )

    projection_df = pd.DataFrame({
        "Year": years,
        "Cumulative Net Position ($)": cumulative_position
    })

    st.subheader("📈 10-Year Net Position Projection")

    base = alt.Chart(projection_df).encode(
        x=alt.X("Year:Q"),
        y=alt.Y("Cumulative Net Position ($):Q")
    )

    projection_line = base.mark_line(point=True)

    zero_line = alt.Chart(
        pd.DataFrame({"y": [0]})
    ).mark_rule(
        strokeWidth=3,
        color="black"
    ).encode(
        y="y:Q"
    )

    chart = (projection_line + zero_line).properties(height=400)

    st.altair_chart(chart, use_container_width=True)

    if adjusted_annual_savings > 0:
        break_even_year = total_spend / adjusted_annual_savings
        st.success(f"📍 Break-even occurs at approximately Year {break_even_year:.2f}")
    else:
        st.warning("⚠️ No positive savings — break-even not achievable.")

with tab_dictionary:

    st.subheader("📘 Harvest Model – Data Dictionary")
    st.markdown(
        """
        This table documents **all calculated fields**, their formulas,
        and the business assumptions used in the Harvest Data Explorer.
        """
    )

    data_dictionary = pd.DataFrame([
        {
            "Field Name": "Yield/Ha",
            "Description": "Yield density per hectare for the selected plant and variety",
            "Formula / Logic": "Total Yield Kg (variety level) ÷ Total Variety Area (ha) per Plant + Variety + Pick Date",
            "Key Assumptions": "Yield/Ha is calculated at variety level to avoid distortion from uneven location-level yield distribution"
        },
        {
            "Field Name": "Cost/Ha",
            "Description": "Total harvest cost per hectare — used to prioritise allocation",
            "Formula / Logic": "Cost Per Kg × Yield/Ha",
            "Key Assumptions": "Varieties with higher Cost/Ha are harvested first to minimise economic exposure"
        },
        {
            "Field Name": "Area_Harvested",
            "Description": "Area harvested based on daily capacity allocation (fill-down by Cost/Ha priority)",
            "Formula / Logic": (
                "Daily capacity (num_machines × session_length × harvest_speed) shared across varieties per plant per day. "
                "Highest Cost/Ha variety fills first. Fully harvested if capacity >= Variety Area, "
                "partially harvested if capacity < Variety Area, not harvested if capacity exhausted."
            ),
            "Key Assumptions": "Each plant has one shared capacity pool per day across all locations"
        },
        {
            "Field Name": "Yield_Lost",
            "Description": "Yield lost due to damage or handling during harvest",
            "Formula / Logic": "Lost/Damaged % × Area_Harvested × Yield/Ha",
            "Key Assumptions": "Loss only applies to area actually harvested — not to unharvested area"
        },
        {
            "Field Name": "Yield_Harvested",
            "Description": "Net harvested yield after accounting for damage and losses",
            "Formula / Logic": "(1 - Lost/Damaged %) × Area_Harvested × Yield/Ha",
            "Key Assumptions": "Loss percentage applies uniformly across harvested area"
        },
        {
            "Field Name": "Combined Platform Run time",
            "Description": "Total platform runtime used to harvest the allocated area",
            "Formula / Logic": "Area_Harvested ÷ Harvest Speed (ha/hr)",
            "Key Assumptions": "Runtime reflects actual harvested area only"
        },
        {
            "Field Name": "Seconds Efficiency",
            "Description": "Proportion of lost yield that becomes true waste",
            "Formula / Logic": "User input (default 90%)",
            "Key Assumptions": "Remaining percentage is recovered as seconds-grade fruit"
        },
        {
            "Field Name": "Budget Sales Price($)",
            "Description": "Budgeted sales price per kg for the given fiscal year and week",
            "Formula / Logic": "Lookup from Sales Budget table by Fiscal Year & Fiscal Week",
            "Key Assumptions": "Budget price reflects expected market value"
        },
        {
            "Field Name": "Opportunity Cost",
            "Description": "Net revenue lost due to damaged fruit",
            "Formula / Logic": (
                "(Budget Sales Price × Yield_Lost × Seconds Efficiency) - "
                "(Overhead % × Cost Per Kg × Yield_Lost + Packaging Cost × Yield_Lost × Seconds Efficiency)"
            ),
            "Key Assumptions": "Lost yield incurs avoided costs (packaging & overhead)"
        },
        {
            "Field Name": "Platform Kg/hour",
            "Description": "Harvest productivity rate of the platform",
            "Formula / Logic": "Yield_Harvested ÷ Combined Platform Run time",
            "Key Assumptions": "Productivity is stable across the harvesting session"
        },
        {
            "Field Name": "Platform cost/kg",
            "Description": "Labour cost per kg using platform harvesting",
            "Formula / Logic": "(Staff Wages ÷ Machine-to-Staff Ratio) ÷ Platform Kg/hour",
            "Key Assumptions": "Staff are evenly distributed across machines"
        },
        {
            "Field Name": "Daily harvest savings",
            "Description": "Cost savings achieved by platform harvesting versus baseline",
            "Formula / Logic": "Yield_Harvested × (Baseline Cost/kg - Platform cost/kg)",
            "Key Assumptions": "Baseline cost reflects traditional harvesting; clipped at 0"
        },
        {
            "Field Name": "Savings - Yield loss cost",
            "Description": "Net economic benefit after accounting for lost yield",
            "Formula / Logic": "Daily harvest savings - Opportunity Cost",
            "Key Assumptions": "Negative values retained (not clipped)"
        },
        {
            "Field Name": "Pick Date",
            "Description": "Date on which harvesting occurred",
            "Formula / Logic": "Converted to date format (YYYY-MM-DD)",
            "Key Assumptions": "Time of day is not analytically relevant"
        },
        {
            "Field Name": "Current Footprint (Ha)",
            "Description": "Total planted area for selected plants",
            "Formula / Logic": "Average ha per Pick Event → Max per Location+Variety block → Sum across all blocks",
            "Key Assumptions": "Uses full FY2025 data regardless of week filter to capture true planted footprint"
        }
    ])

    st.dataframe(
        data_dictionary,
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "ℹ️ All percentages, costs, and efficiencies are user-adjustable "
        "to support scenario testing and sensitivity analysis."
    )
