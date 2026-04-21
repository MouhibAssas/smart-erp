import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import "./Layout.css";

const navItems = [
  { to: "/chat",      label: "Chat",      icon: "💬" },
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/admin",     label: "Admin",     icon: "👥" },
];

export default function Layout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const closeMobileMenu = () => setMobileMenuOpen(false);

  return (
    <div className="layout-root">
      <button
        type="button"
        className="layout-mobile-toggle"
        aria-label="Open menu"
        aria-expanded={mobileMenuOpen}
        onClick={() => setMobileMenuOpen(true)}
      >
        <span />
        <span />
        <span />
      </button>

      {mobileMenuOpen && (
        <button
          type="button"
          className="layout-backdrop"
          aria-label="Close menu"
          onClick={closeMobileMenu}
        />
      )}

      <aside className={"layout-sidebar" + (mobileMenuOpen ? " open" : "")}>
        <div className="layout-logo">Smart ERP</div>

        <button
          type="button"
          className="layout-mobile-close"
          aria-label="Close menu"
          onClick={closeMobileMenu}
        >
          ✕
        </button>

        <nav className="layout-nav">
          <span className="layout-nav-label">Menu</span>
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={closeMobileMenu}
              className={({ isActive }) =>
                "layout-nav-item" + (isActive ? " active" : "")
              }
            >
              <span className="layout-nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="layout-main">
        <Outlet />  {/* ← your page renders here */}
      </main>
    </div>
  );
}