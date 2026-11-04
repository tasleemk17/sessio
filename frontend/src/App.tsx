import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ExpertPage from "./pages/ExpertPage";
import ExpertStudio from "./pages/ExpertStudio";
import Home from "./pages/Home";
import Login from "./pages/Login";
import { Contact, Privacy, RefundPolicy, Terms } from "./pages/Policies";
import Bookings from "./pages/seeker/Bookings";
import { Categories, FindPeople } from "./pages/seeker/Find";
import Memberships from "./pages/seeker/Memberships";
import Profile from "./pages/seeker/Profile";
import Rewards from "./pages/seeker/Rewards";
import SeekerHome from "./pages/seeker/SeekerHome";
import SeekerLayout from "./pages/seeker/SeekerLayout";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="e/:handle" element={<ExpertPage />} />
        <Route path="dashboard" element={<SeekerLayout />}>
          <Route index element={<Navigate to="home" replace />} />
          <Route path="home" element={<SeekerHome />} />
          <Route path="bookings/:type?/:sub?" element={<Bookings />} />
          <Route path="memberships" element={<Memberships />} />
          <Route path="find" element={<FindPeople />} />
          <Route path="profile" element={<Profile />} />
          <Route path="rewards" element={<Rewards />} />
          <Route path="categories" element={<Categories />} />
          <Route path="*" element={<Navigate to="home" replace />} />
        </Route>
        <Route path="expert/:tab?" element={<ExpertStudio />} />
        <Route path="login" element={<Login />} />
        <Route path="contact" element={<Contact />} />
        <Route path="terms" element={<Terms />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="refund-policy" element={<RefundPolicy />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
