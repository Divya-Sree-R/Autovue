import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import "./App.css";

import AppLayout from "./components/layout/AppLayout";

import AnalyzePage from "./pages/AnalyzePage";
import EvidencePage from "./pages/EvidencePage";
import EvaluationPage from "./pages/EvaluationPage";
import OverviewPage from "./pages/OverviewPage";
import ResultsPage from "./pages/ResultsPage";
import SystemPage from "./pages/SystemPage";


function App() {
  return (
    <BrowserRouter>

      <Routes>

        <Route element={<AppLayout />}>

          <Route
            index
            element={<OverviewPage />}
          />

          <Route
            path="analyze"
            element={<AnalyzePage />}
          />

          <Route
            path="results"
            element={<ResultsPage />}
          />

          <Route
            path="evidence"
            element={<EvidencePage />}
          />

          <Route
            path="evaluation"
            element={<EvaluationPage />}
          />

          <Route
            path="system"
            element={<SystemPage />}
          />

        </Route>


        <Route
          path="*"
          element={
            <Navigate
              to="/"
              replace
            />
          }
        />

      </Routes>

    </BrowserRouter>
  );
}


export default App;
