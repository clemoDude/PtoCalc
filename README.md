# PtoCalc

PtoCalc is a PTO planning tool that projects weekly balances using accrual rules, PTO caps, rollover limits, work schedules, holidays, and planned time off.

## React App

The primary app is now a React + TypeScript single-page app intended for static hosting.

### Local development

```bash
npm install
npm run dev
```

### Production build

```bash
npm run build
```

Amplify Hosting can build the app from this repo using `amplify.yml`.

## Legacy Streamlit App

`PtoCalc.py` is still in the repo as a reference implementation while the React version is validated for parity.
