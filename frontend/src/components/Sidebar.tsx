import type { MouseEvent } from "react";
import { Link } from "@tanstack/react-router";
import { Clapperboard, Cpu, Film, Layers3, Settings, ShieldCheck } from "lucide-react";

export type SidebarTab = "all" | "review" | "completed" | "configuration";

export function Sidebar({
  active,
  waitingCount,
  health,
  onTab,
}: {
  active: SidebarTab;
  waitingCount: number;
  health?: { provider: string; database: string };
  /** When on the "/" route, switch tabs in place instead of re-navigating. */
  onTab?: (tab: "all" | "review" | "completed") => void;
}) {
  const navProps = (tab: "all" | "review" | "completed") =>
    onTab
      ? {
          onClick: (event: MouseEvent) => {
            event.preventDefault();
            onTab(tab);
          },
        }
      : {};
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
      <Link
        className={active === "all" ? "nav active" : "nav"}
        to="/"
        {...navProps("all")}
      >
        <Layers3 size={18} /> Production
      </Link>
      <Link
        className={active === "review" ? "nav active" : "nav"}
        to="/"
        {...navProps("review")}
      >
        <ShieldCheck size={18} /> Review queue{" "}
        <span className="count">{waitingCount}</span>
      </Link>
      <Link
        className={active === "completed" ? "nav active" : "nav"}
        to="/"
        {...navProps("completed")}
      >
        <Film size={18} /> Completed
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
