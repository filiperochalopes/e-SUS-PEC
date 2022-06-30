import { createGlobalStyle } from "styled-components";

export const GlobalStyles = createGlobalStyle`

  @import url('https://fonts.googleapis.com/css?family=Raleway:400,700&display=swap');
  @import url('https://fonts.googleapis.com/css?family=Arvo:400,700&display=swap');

  *{
    margin: 0;
    padding: 0;
    font-family: 'Raleway', sans-serif;
  }
  html, body, #root{
    height: 100%;
    background: ${(props) => props.theme.white};
  }

  h1{
    color: ${(props) => props.theme.black};
  }

  input {
    outline: none;
    border: none;
    border-radius: 10px;
    background: #f0f0f0;
    padding: 4px 8px;

    &::placeholder{
      color: ${(props) => props.theme.black};
    }
  }

  .flex {
    display: flex;
    &.space-between { justify-content: space-between }
    &.align-end { align-items: flex-end }
    &.justify-end { justify-content: flex-end }
    &.center { align-items: center }
  }

  /* Change Autocomplete styles in Chrome*/
  input:-webkit-autofill,
  input:-webkit-autofill:hover,
  input:-webkit-autofill:focus,
  textarea:-webkit-autofill,
  textarea:-webkit-autofill:hover,
  textarea:-webkit-autofill:focus,
  select:-webkit-autofill,
  select:-webkit-autofill:hover,
  select:-webkit-autofill:focus {
    border: none;
    /* -webkit-text-fill-color: #fff; */
    -webkit-box-shadow: 0 0 0px 1000px trasparent inset;
    transition: background-color 5000s ease-in-out 0s;
    font-size: unset;
  }
`;
