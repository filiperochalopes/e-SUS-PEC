import { Form } from "./styles";

import Button from "components/Button";
import TextInput from "components/TextInput";
import { Formik } from "formik";
import React from "react";
import { useNavigate } from "react-router-dom";

export default () => {
  let navigate = useNavigate();
  return (
    <>
      <h1>Esqueci minha senha</h1>
      <Formik
        initialValues={{ email: "" }}
        onSubmit={(values, actions) => {
          alert(JSON.stringify(values, null, 2));
          navigate("/senha-enviada", { replace: false });
        }}
      >
        {() => (
          <Form>
            <TextInput type="email" name="email" placeholder="Email" />

            <Button type="submit">Submit</Button>
          </Form>
        )}
      </Formik>
    </>
  );
};
