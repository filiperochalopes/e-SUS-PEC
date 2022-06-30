import { TextInput } from "./styles";

import { Field } from "formik";
import PropTypes from "prop-types";
import React from "react";

const Input = ({ className, type, name, placeholder }) => (
  <TextInput className={className}>
    <Field type={type} name={name} placeholder={placeholder} />
  </TextInput>
);

Input.propTypes = {
  name: PropTypes.string.isRequired,
  className: PropTypes.string,
  type: PropTypes.string,
  placeholder: PropTypes.string,
};

Input.defaultProps = {
  className: "",
  type: "text",
  placeholder: "placeholder",
};

export default Input;
