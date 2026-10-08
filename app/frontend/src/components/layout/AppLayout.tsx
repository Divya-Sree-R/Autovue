import {
  NavLink,
  Outlet,
} from "react-router-dom";


const navigation = [
  {
    to: "/",
    label: "Overview",
    end: true,
  },
  {
    to: "/analyze",
    label: "Analyze Video",
  },
  {
    to: "/results",
    label: "Recognition Results",
  },
  {
    to: "/evidence",
    label: "Evidence Review",
  },
  {
    to: "/evaluation",
    label: "Evaluation",
  },
  {
    to: "/system",
    label: "System",
  },
];


function AppLayout() {
  return (
    <div className="app-shell">

      <aside className="sidebar">

        <div className="brand">

          <div className="brand-mark">
            AV
          </div>

          <div>
            <h1>AutoVue</h1>
            <p>Indian ANPR</p>
          </div>

        </div>


        <nav>
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive
                  ? "nav-link nav-active"
                  : "nav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>


        <div className="sidebar-footer">
          <span>M25 Reference Run</span>
          <small>
            Frozen unseen-road evaluation
          </small>
        </div>

      </aside>


      <main className="content">
        <Outlet />
      </main>

    </div>
  );
}


export default AppLayout;
