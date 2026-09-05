import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Dashboard from "./pages/Dashboard";
import EmbedReport from "./pages/EmbedReport";
import Login from "./pages/Login";
import PrReport from "./pages/PrReport";
import RepoDetail from "./pages/RepoDetail";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/repos/:owner/:repo" element={<ProtectedRoute><RepoDetail /></ProtectedRoute>} />
        <Route path="/repos/:owner/:repo/pulls/:number" element={<ProtectedRoute><PrReport /></ProtectedRoute>} />
        <Route path="/embed/repos/:owner/:repo/pulls/:number" element={<EmbedReport />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
