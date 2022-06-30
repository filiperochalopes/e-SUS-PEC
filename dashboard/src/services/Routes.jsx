import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import DashboardIndex from "views/Dashboard";
import ForgotPass from "views/ForgotPass";
import Login from "views/Login";
import SentPass from "views/SentPass";

export default () => {
  return (
    <Routes>
      <Route exact path="/" element={<Navigate to="/login" replace />} />
      <Route exact path="/login" element={<Login />} />
      <Route exact path="/esqueci-minha-senha" element={<ForgotPass />} />
      <Route exact path="/senha-enviada" element={<SentPass />} />
      <Route exact path="/dashboard" element={<DashboardIndex />} />
    </Routes>
  );
};
