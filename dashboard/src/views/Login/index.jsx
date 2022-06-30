/* eslint-disable jsx-a11y/label-has-associated-control */
import { Form } from "./styles";

import AppContext from "services/context";

import Button from "components/Button";
import TextInput from "components/TextInput";
import { Formik } from "formik";
import React, { useContext } from "react";
import { Link, useNavigate } from "react-router-dom";

const Login = () => {
  const context = useContext(AppContext);
  const navigate = useNavigate();

  return (
    <>
      <h1>Login</h1>
      {process.env.REACT_APP_API_URL}
      <Formik
        initialValues={{ email: "", pass: "" }}
        onSubmit={(values, actions) => {
          setTimeout(() => {
            alert(JSON.stringify(values, null, 2));
            actions.setSubmitting(false);
            context.setSigned(true);
            navigate("/dashboard");
          }, 1000);
        }}
      >
        {() => (
          <Form>
            <TextInput type="email" name="email" placeholder="Email" />

            <TextInput type="password" name="pass" placeholder="Senha" />

            <Button type="submit">Submit</Button>

            <Link to="/esqueci-minha-senha">Esqueci minha senha</Link>
          </Form>
        )}
      </Formik>

      <Link to="/">Não possui cadastro? Cadastrar</Link>
    </>
  );
};

export default Login;
