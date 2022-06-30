import { Container } from "./styles";

import PropTypes from "prop-types";
import React from "react";

const Login = ({ children }) => <Container>{children}</Container>;

Login.propTypes = {
  children: PropTypes.elementType.isRequired,
};

export default Login;
