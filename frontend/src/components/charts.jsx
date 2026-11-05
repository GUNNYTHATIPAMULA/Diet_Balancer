import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MACRO_COLORS } from "../utils/constants";
import { shortDay } from "../utils/format";

const axis = { stroke: "#8A988E", fontSize: 12, tickLine: false, axisLine: false };
const tooltipStyle = { borderRadius: 14, border: "1px solid #E2E9E1", boxShadow: "0 8px 24px -12px rgba(31,95,63,.3)", fontSize: 13 };

export function MealCaloriesChart({ meals }) {
  const rows = meals.map((m) => ({ name: m.meal_type[0].toUpperCase() + m.meal_type.slice(1), kcal: Math.round(m.totals.calories) }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={rows} margin={{ top: 8, right: 4, left: -18, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#EEF2ED" />
        <XAxis dataKey="name" {...axis} />
        <YAxis {...axis} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#F4F7F2" }} formatter={(v) => [`${v} kcal`, "Calories"]} />
        <Bar dataKey="kcal" fill={MACRO_COLORS.calories} radius={[10, 10, 4, 4]} maxBarSize={44} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function MacroDonut({ split, totals }) {
  const rows = [
    { name: "Protein", value: split.protein, grams: totals.protein_g, color: MACRO_COLORS.protein },
    { name: "Carbs", value: split.carbs, grams: totals.carbs_g, color: MACRO_COLORS.carbs },
    { name: "Fat", value: split.fat, grams: totals.fat_g, color: MACRO_COLORS.fat },
  ];
  const empty = rows.every((r) => !r.value);
  return (
    <div className="flex items-center gap-4">
      <div className="h-[180px] w-[180px] shrink-0">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={empty ? [{ value: 1 }] : rows} dataKey="value" innerRadius={56} outerRadius={84} paddingAngle={empty ? 0 : 3} stroke="none" isAnimationActive={!empty}>
              {(empty ? [{ color: "#E2E9E1" }] : rows).map((r, i) => <Cell key={i} fill={r.color} />)}
            </Pie>
            {!empty && <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [`${v}% of calories`, n]} />}
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-3 text-sm">
        {rows.map((r) => (
          <li key={r.name}>
            <span className="flex items-center gap-2 font-semibold"><span className="h-2.5 w-2.5 rounded-full" style={{ background: r.color }} />{r.name}</span>
            <span className="num ml-[18px] text-slate">{r.value}% · {Math.round(r.grams)} g</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TargetVsActualChart({ days, target, height = 240 }) {
  const rows = days.map((d) => ({ day: shortDay(d.date), kcal: Math.round(d.calories) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 12, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#EEF2ED" />
        <XAxis dataKey="day" {...axis} interval="preserveStartEnd" />
        {/* Always include the target in the axis range so the target line is visible. */}
        <YAxis {...axis} domain={[0, (dataMax) => Math.ceil(Math.max(dataMax, (target || 0) * 1.12) / 100) * 100]} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#F4F7F2" }} formatter={(v) => [`${v} kcal`, "Eaten"]} />
        <Bar dataKey="kcal" radius={[8, 8, 3, 3]} maxBarSize={36}>
          {rows.map((r, i) => (
            <Cell key={i} fill={target && r.kcal > target * 1.1 ? "#D08A7E" : MACRO_COLORS.calories} />
          ))}
        </Bar>
        {target && <ReferenceLine y={target} stroke="#1F5F3F" strokeDasharray="6 4" strokeWidth={1.5}
          label={{ value: `Target ${target}`, position: "insideTopRight", fill: "#1F5F3F", fontSize: 12 }} />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function MacroTrendChart({ days, height = 240 }) {
  const rows = days.map((d) => ({ day: shortDay(d.date), Protein: Math.round(d.protein_g), Carbs: Math.round(d.carbs_g), Fat: Math.round(d.fat_g) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#EEF2ED" />
        <XAxis dataKey="day" {...axis} interval="preserveStartEnd" />
        <YAxis {...axis} unit=" g" />
        <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [`${v} g`, n]} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 13 }} />
        <Line type="monotone" dataKey="Protein" stroke={MACRO_COLORS.protein} strokeWidth={2.5} dot={false} />
        <Line type="monotone" dataKey="Carbs" stroke={MACRO_COLORS.carbs} strokeWidth={2.5} dot={false} />
        <Line type="monotone" dataKey="Fat" stroke={MACRO_COLORS.fat} strokeWidth={2.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
