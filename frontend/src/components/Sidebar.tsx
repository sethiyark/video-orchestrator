import { Link } from "@tanstack/react-router";
import {
  BookOpen,
  Clapperboard,
  Cpu,
  Film,
  Layers3,
  Settings,
  ShieldCheck,
} from "lucide-react";

export type SidebarTab =
  | "production"
  | "review"
  | "completed"
  | "series"
  | "configuration"
  | "none";

export function Sidebar({
  active,
  waitingCount,
  health,
}: {
  active: SidebarTab;
  waitingCount: number;
  health?: { provider: string; database: string };
}) {
  return (
    <aside className="sidebar">
      <Link className="brand" to="/">
        <span className="brand-icon">
          <Clapperboard size={22} />
        </span>
        framecraft<span className="brand-dot">.</span>
      </Link>
      <div className="workspace">
        <span className="avatar">S</span>
        <div>
          My studio<small>Single-channel workspace</small>
        </div>
      </div>
      <div className="nav-label">WORKSPACE</div>
      <Link className={active === "production" ? "nav active" : "nav"} to="/production">
        <Layers3 size={18} /> Production
      </Link>
      <Link className={active === "review" ? "nav active" : "nav"} to="/review">
        <ShieldCheck size={18} /> Review queue{" "}
        <span className="count">{waitingCount}</span>
      </Link>
      <Link className={active === "completed" ? "nav active" : "nav"} to="/completed">
        <Film size={18} /> Completed
      </Link>
      <Link className={active === "series" ? "nav active" : "nav"} to="/series">
        <BookOpen size={18} /> Series
      </Link>
      <Link
        className={active === "configuration" ? "nav active" : "nav"}
        to="/configuration"
      >
        <Settings size={18} /> Configuration
      </Link>
      <div className="local-card">
        <Cpu size={22} />
        <strong>Local by design</strong>
        <p>
          One workload at a time.
          <br />
          Built for your 8 GB GPU.
        </p>
        <span className="mock-dot" />{" "}
        {health ? `${health.provider} providers · ${health.database}` : "Checking backend…"}
      </div>
      <footer>FRAMECRAFT / v0.1</footer>
    </aside>
  );
}
