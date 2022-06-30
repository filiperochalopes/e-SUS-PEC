import AppContext from "services/context";

import React, { useContext } from "react";
import { Navigate } from "react-router-dom";

export default ({ children }) => {
  const { signed } = useContext(AppContext);
  console.log(signed);

  if (!signed) {
    return <Navigate to="/" replace />;
  }

  return <section>{children}</section>;
};
