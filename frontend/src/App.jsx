import "./styles/global.css";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import NavBar from "./components/Navbar.jsx";
import PaySuccess from "./components/PaySuccess";
import { MeProvider } from "./context/MeContext.jsx";
import PayCancel from "./components/PayCancel.jsx";
import ResumeConstructor from "./components/ResumeConstructor.jsx";
import AuthCallback from "./services/AuthCallback.jsx";

export default function App() {
   return (
    <MeProvider>
      <Router>
        <div>
          <NavBar />
          <Routes>
            {/* <Route path="/" element={<Analyze />} /> */}
            <Route path="/" element={<ResumeConstructor />} />
            <Route path="/auth/callback" element={<AuthCallback />} />

            <Route path="/pay/success" element={<PaySuccess />} />
            <Route path="/pay/cancel" element={<PayCancel />} />

          </Routes>
        </div>
      </Router>
    </MeProvider>
  );
}

