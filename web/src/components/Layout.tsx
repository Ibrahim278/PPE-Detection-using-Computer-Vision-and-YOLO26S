import { BarChart3, Cpu, HardHat, ScanSearch, Video } from "lucide-react";
import { NavLink, Outlet } from "react-router";

const NAV = [
  { to: "/", label: "Live Monitor", icon: Video, end: true },
  { to: "/analyze", label: "Analyze", icon: ScanSearch },
  { to: "/violations", label: "Violations", icon: BarChart3 },
  { to: "/model", label: "Model", icon: Cpu },
];

export default function Layout() {
  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <aside className="sticky top-0 z-10 border-b border-line bg-panel md:h-screen md:w-60 md:shrink-0 md:border-r md:border-b-0">
        <div className="flex items-center gap-2 px-4 py-3 md:px-5 md:py-5">
          <span className="grid size-8 place-items-center rounded-lg bg-brand text-brand-ink"><HardHat size={18} aria-hidden /></span>
          <div>
            <div className="font-semibold leading-tight">SiteGuard</div>
            <div className="text-xs text-muted">PPE compliance</div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:px-3" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => `flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition
                ${isActive ? "bg-brand/15 text-brand" : "text-muted hover:bg-panel-2 hover:text-ink"}`}>
              <Icon size={17} aria-hidden /> {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-7xl"><Outlet /></div>
      </main>
    </div>
  );
}
