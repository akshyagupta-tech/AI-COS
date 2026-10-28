from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


def _get_student_life_data(
    api_url: str,
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{api_url}{path}", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as error:
        response = error.response
        if response is not None and response.status_code == 502:
            st.warning(
                "The campus server is currently waking up from sleep mode. "
                "Please wait 50 seconds and try again."
            )
        elif response is not None and "text/html" in response.headers.get("Content-Type", "").lower():
            st.error("The student-life service returned an unexpected response. Please try again shortly.")
        else:
            detail = response.text if response is not None else str(error)
            st.error(f"Student-life service error: {detail}")
    except requests.RequestException as error:
        st.error(f"Could not reach the AI-COS API at {api_url}. ({error})")
    return None


def render_student_life_ui(api_url: str) -> None:
    st.markdown('<div class="eyebrow">AI-COS / RESIDENTIAL & DINING</div>', unsafe_allow_html=True)
    st.title("Student life operations")
    st.markdown(
        '<div class="subtle">Forecast demand, create stable roommate pairs, schedule shared amenities, and reduce cafeteria waits.</div>',
        unsafe_allow_html=True,
    )
    resource_catalog = [
        "Mess forecast",
        "Roommate matching",
        "Amenity scheduler",
        "Cafeteria queue",
    ]
    search_term = st.text_input("Quick Resource Finder", placeholder="Search a student-life tool…")
    if search_term:
        filtered_resources = [
            item for item in resource_catalog if search_term.lower() in item.lower()
        ]
        if filtered_resources:
            st.caption(f"{len(filtered_resources)} matching tools")
            st.write(", ".join(filtered_resources))
        else:
            st.info("No matching tools found for that search.")
    st.divider()
    tabs = st.tabs(["Mess forecast", "Roommate matching", "Amenity scheduler", "Cafeteria queue"])

    with tabs[0]:
        st.subheader("Dinner demand and food-waste forecast")
        controls = st.columns(2)
        sections = controls[0].number_input("Scheduled evening sections", 0, 60, 22, key="sl-sections")
        window = controls[1].slider("Moving-average window (days)", 3, 14, 7, key="sl-window")
        if st.button("Forecast dinner demand", key="sl-forecast", type="primary"):
            data = _get_student_life_data(
                api_url,
                "/student-life/mess/forecast",
                {"scheduled_sections": sections, "window": window},
            )
            if data:
                st.session_state["sl-mess-result"] = data
        data = st.session_state.get("sl-mess-result")
        if data:
            metrics = st.columns(3)
            metrics[0].metric("Predicted dinner diners", data["predicted_diners"])
            metrics[1].metric("Moving-average baseline", data["moving_average_diners"])
            metrics[2].metric("Estimated waste", f"{data['estimated_food_waste_kg']} kg")
            history = pd.DataFrame(data["history"])
            history["series"] = history["day"].map(lambda day: "Forecast" if day == "Forecast" else "History")
            chart = px.line(
                history,
                x="day",
                y="dinner_diners",
                color="series",
                markers=True,
                title="Dinner attendance history and forecast",
                color_discrete_map={"History": "#1e6253", "Forecast": "#d87254"},
            )
            chart.update_layout(
                plot_bgcolor="rgba(255,255,255,0)",
                paper_bgcolor="rgba(255,255,255,0)",
                font_color="#193a35",
                margin={"l": 12, "r": 12, "t": 48, "b": 12},
            )
            st.plotly_chart(chart, use_container_width=True)
            st.dataframe(history, use_container_width=True, hide_index=True)
            st.caption(data["algorithm"])

    with tabs[1]:
        st.subheader("Stable roommate pairings")
        st.markdown("Pairings balance preferences across quiet, cleanliness, sleep, social, and study habits.")
        if st.button("Calculate stable pairings", key="sl-roommates", type="primary"):
            data = _get_student_life_data(api_url, "/student-life/roommates/matches")
            if data:
                st.session_state["sl-roommate-result"] = data
        data = st.session_state.get("sl-roommate-result")
        if data:
            metrics = st.columns(2)
            metrics[0].metric("Roommate pairs", data["pair_count"])
            metrics[1].metric("Proposals made", data["proposal_count"])
            pairings = pd.DataFrame(data["pairings"])
            st.dataframe(pairings, use_container_width=True, hide_index=True)
            chart = px.bar(
                pairings,
                x="student_a",
                y="compatibility_pct",
                color="student_b",
                title="Mutual roommate compatibility",
                color_discrete_sequence=["#1e6253", "#d87254", "#3f80a6", "#e3b45c"],
            )
            chart.update_layout(
                plot_bgcolor="rgba(255,255,255,0)",
                paper_bgcolor="rgba(255,255,255,0)",
                font_color="#193a35",
                margin={"l": 12, "r": 12, "t": 48, "b": 12},
            )
            st.plotly_chart(chart, use_container_width=True)
            st.caption(data["algorithm"])

    with tabs[2]:
        st.subheader("Fair shared-amenity bookings")
        amenity = st.selectbox(
            "Amenity",
            ["washing_machine", "sports_court"],
            format_func=lambda value: value.replace("_", " ").title(),
            key="sl-amenity",
        )
        if st.button("Build booking schedule", key="sl-schedule", type="primary"):
            data = _get_student_life_data(api_url, "/student-life/amenities/schedule", {"amenity": amenity})
            if data:
                st.session_state["sl-amenity-result"] = data
        data = st.session_state.get("sl-amenity-result")
        if data and data["amenity"] == amenity:
            metrics = st.columns(3)
            metrics[0].metric("Booked", data["booked_count"])
            metrics[1].metric("Waitlisted", data["waitlisted_count"])
            metrics[2].metric("Capacity per slot", data["capacity_per_slot"])
            schedule = pd.DataFrame(data["schedule"])
            st.dataframe(schedule, use_container_width=True, hide_index=True)
            allocation = pd.DataFrame(
                [
                    {"status": "Booked", "requests": data["booked_count"]},
                    {"status": "Waitlisted", "requests": data["waitlisted_count"]},
                ]
            )
            chart = px.pie(
                allocation,
                names="status",
                values="requests",
                hole=0.46,
                title="Amenity slot allocation",
                color="status",
                color_discrete_map={"Booked": "#1e6253", "Waitlisted": "#d87254"},
            )
            st.plotly_chart(chart, use_container_width=True)
            st.caption(data["algorithm"])

    with tabs[3]:
        st.subheader("Queue load and dynamic menu pricing")
        controls = st.columns(3)
        arrivals = controls[0].number_input("Arrivals in the last 15 minutes", 0, 500, 9, key="sl-arrivals")
        counters = controls[1].number_input("Open service counters", 1, 20, 4, key="sl-counters")
        service_time = controls[2].number_input(
            "Average service time (minutes)", 0.5, 30.0, 3.0, step=0.5, key="sl-service-time"
        )
        if st.button("Estimate cafeteria wait", key="sl-queue", type="primary"):
            data = _get_student_life_data(
                api_url,
                "/student-life/cafeteria/queue",
                {"arrivals_last_15m": arrivals, "open_counters": counters, "service_minutes": service_time},
            )
            if data:
                st.session_state["sl-queue-result"] = data
        data = st.session_state.get("sl-queue-result")
        if data:
            metrics = st.columns(4)
            metrics[0].metric(
                "Estimated wait",
                "Over capacity" if data["estimated_wait_minutes"] is None else f"{data['estimated_wait_minutes']} min",
            )
            metrics[1].metric("Counter utilization", f"{data['utilization_pct']}%")
            metrics[2].metric("Pricing state", data["pricing_state"].replace("_", " ").title())
            metrics[3].metric("Off-peak discount", f"{data['discount_pct']}%")
            menu = pd.DataFrame(data["menu"])
            st.dataframe(menu, use_container_width=True, hide_index=True)
            chart = px.bar(
                menu,
                x="item",
                y="dynamic_price",
                color="discount_pct",
                title="Price by queue state",
                labels={"dynamic_price": "Price", "discount_pct": "Discount (%)"},
                color_continuous_scale=["#d87254", "#82b9a2", "#1e6253"],
            )
            chart.update_layout(
                plot_bgcolor="rgba(255,255,255,0)",
                paper_bgcolor="rgba(255,255,255,0)",
                font_color="#193a35",
                margin={"l": 12, "r": 12, "t": 48, "b": 12},
            )
            st.plotly_chart(chart, use_container_width=True)
            st.caption(data["algorithm"])