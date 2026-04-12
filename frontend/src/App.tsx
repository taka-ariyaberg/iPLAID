import { Link, Route, Routes } from "react-router-dom";

import { ResultsPage } from "./pages/ResultsPage";
import { WorkbenchPage } from "./pages/WorkbenchPage";
import "./styles/App.css";
import { WorkbenchStateProvider } from "./workbenchState";

export default function App() {
  return (
    <WorkbenchStateProvider>
      <div className="app-shell">
        <header className="app-header">
          <div className="app-brand">
            <p className="app-kicker">iPLAID</p>
          </div>
          <nav className="app-nav">
            <Link to="/">Workbench</Link>
          </nav>
        </header>

        <main className="app-main">
          <Routes>
            <Route path="/" element={<WorkbenchPage />} />
            <Route path="/runs/:jobId" element={<ResultsPage />} />
          </Routes>
        </main>
      </div>
    </WorkbenchStateProvider>
  );
}
