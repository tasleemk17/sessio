import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import ExpertPage from "./pages/ExpertPage";
import ExpertStudio from "./pages/ExpertStudio";
import Home from "./pages/Home";
import Login from "./pages/Login";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="e/:handle" element={<ExpertPage />} />
        <Route path="dashboard/:tab?" element={<Dashboard />} />
        <Route path="expert/:tab?" element={<ExpertStudio />} />
        <Route path="login" element={<Login />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
