import Analyze from "./pages/Analyze.jsx";
import "./styles/global.css";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import NavBar from "./components/Navbar.jsx";
import PaySuccess from "./components/PaySuccess";


export default function App() {
  return (
        
    <Router>
      <div>
        <NavBar />
        <Routes>
          <Route path="/" element={<Analyze />} />
          <Route path="/pay/success" element={<PaySuccess />} />
        </Routes>
      </div>
    </Router>
  );
}

