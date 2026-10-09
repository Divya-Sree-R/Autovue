import {
  useEffect,
  useState,
} from "react";

import {
  NavLink,
  Outlet,
} from "react-router-dom";

import {
  API_BASE,
} from "../../services/api";


const navigation = [
  {
    to: "/",
    label: "Overview",
    end: true,
  },
  {
    to: "/analyze",
    label: "Analyze",
  },
  {
    to: "/results",
    label: "Results",
  },
  {
    to: "/evidence",
    label: "Evidence",
  },
  {
    to: "/evaluation",
    label: "Analytics",
  },
];


function AppLayout() {

  const [
    apiOnline,
    setApiOnline,
  ] = useState<boolean | null>(
    null
  );


  useEffect(() => {

    let cancelled = false;


    async function checkHealth() {

      try {

        const response = await fetch(
          `${API_BASE}/health`
        );

        if (!cancelled) {
          setApiOnline(
            response.ok
          );
        }

      } catch {

        if (!cancelled) {
          setApiOnline(
            false
          );
        }

      }
    }


    void checkHealth();


    const timer =
      window.setInterval(
        () => {
          void checkHealth();
        },
        15000
      );


    return () => {
      cancelled = true;

      window.clearInterval(
        timer
      );
    };

  }, []);


  return (
    <div className="app-shell">

      <div className="app-frame">

        <header className="app-header">

          <div className="brand">

            <div className="brand-mark">
              <span />
            </div>

            <div className="brand-copy">

              <strong>
                AutoVue
              </strong>

              <small>
                Indian ANPR Intelligence
              </small>

            </div>

          </div>


          <nav
            className="primary-nav"
            aria-label="Primary navigation"
          >

            {navigation.map(
              (item) => (

                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={
                    ({ isActive }) =>
                      isActive
                        ? "nav-link nav-active"
                        : "nav-link"
                  }
                >
                  {item.label}
                </NavLink>

              )
            )}

          </nav>


          <div className="header-actions">

            <div
              className={
                apiOnline === true
                  ? "api-pill api-pill-online"
                  : apiOnline === false
                  ? "api-pill api-pill-offline"
                  : "api-pill"
              }
            >

              <span
                className="api-indicator"
              />

              <span>
                {apiOnline === true
                  ? "API Online"
                  : apiOnline === false
                  ? "API Offline"
                  : "Checking API"}
              </span>

            </div>


            <NavLink
              to="/system"
              className={
                ({ isActive }) =>
                  isActive
                    ? "system-button system-active"
                    : "system-button"
              }
              aria-label="System"
              title="System"
            >

              <svg
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  d="M12 8.25a3.75 3.75 0 1 0 0 7.5 3.75 3.75 0 0 0 0-7.5Zm8.25 3.75c0-.58-.06-1.15-.18-1.7l2.02-1.58-2-3.46-2.47.99a8.33 8.33 0 0 0-2.94-1.7L14.3 1.9h-4.6l-.38 2.65a8.33 8.33 0 0 0-2.94 1.7l-2.47-.99-2 3.46 2.02 1.58a8.2 8.2 0 0 0 0 3.4l-2.02 1.58 2 3.46 2.47-.99a8.33 8.33 0 0 0 2.94 1.7l.38 2.65h4.6l.38-2.65a8.33 8.33 0 0 0 2.94-1.7l2.47.99 2-3.46-2.02-1.58c.12-.55.18-1.12.18-1.7Z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.55"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>

            </NavLink>

          </div>

        </header>


        <main className="content">
          <Outlet />
        </main>

      </div>

    </div>
  );
}


export default AppLayout;
