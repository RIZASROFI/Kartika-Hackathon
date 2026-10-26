import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import AnalysisDetail from "./pages/AnalysisDetail";
import Analyses from "./pages/Analyses";
import Dashboard from "./pages/Dashboard";
import Methodology from "./pages/Methodology";
import NewAnalysis from "./pages/NewAnalysis";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="analisis" element={<Analyses />} />
        <Route path="analisis/baru" element={<NewAnalysis />} />
        <Route path="analisis/:id" element={<AnalysisDetail />} />
        <Route path="metodologi" element={<Methodology />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
