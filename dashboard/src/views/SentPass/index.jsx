import { Container } from "./styles";

import React from "react";
import { Link } from "react-router-dom";

const ForgotPass = () => (
  <Container>
    <p>
      Foi enviado um e-mail para você. Siga as orientações para o resgate da sua
      senha.
    </p>
    <Link to="/">Login</Link>
  </Container>
);

export default ForgotPass;
