import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function PayCancel() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/?status=cancelled", { replace: true });
  }, [navigate]);
  return null;
}