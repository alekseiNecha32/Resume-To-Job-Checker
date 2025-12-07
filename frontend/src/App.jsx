import Analyze from "./pages/Analyze.jsx";
import "./styles/global.css";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import NavBar from "./components/Navbar.jsx";
import PaySuccess from "./components/PaySuccess";
import { MeProvider } from "./context/MeContext.jsx";
import PayCancel from "./components/PayCancel.jsx";
import ResumeConstructor from "./components/ResumeConstructor.jsx";

export default function App() {
   return (
    <MeProvider>
      <Router>
        <div>
          <NavBar />
          <Routes>
            <Route path="/" element={<Analyze />} />
            <Route path="/constructor" element={<ResumeConstructor />} />

            <Route path="/pay/success" element={<PaySuccess />} />
            <Route path="/pay/cancel" element={<PayCancel />} />

          </Routes>
        </div>
      </Router>
    </MeProvider>
  );
}

