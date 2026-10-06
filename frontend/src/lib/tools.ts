/** Plain-language names for the assistant's tools, shown while it works. Unknown tools fall back to their id. */
const LABELS: Record<string, string> = {
  get_demand_forecast: "demand forecast",
  get_inventory_position: "inventory position",
  propose_rebalance: "rebalance options",
  list_at_risk_shipments: "shipments at risk",
  get_lane_cost_carbon: "lane cost and carbon",
};

export function toolLabel(name: string): string {
  return LABELS[name] ?? name.replace(/_/g, " ");
}
