import Analyze from "./pages/Analyze.jsx";
import "./styles/global.css";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import NavBar from "./components/Navbar.jsx";


export default function App() {
  return (
        
    <Router>
      <div>
        <NavBar />
        <Routes>
          <Route path="/" element={<Analyze />} />
        </Routes>
      </div>
    </Router>
  );
}

