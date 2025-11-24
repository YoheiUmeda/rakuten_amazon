// src/App.tsx
import React from "react";
import PriceSearchPage from "./components/PriceSearchPage";

const App: React.FC = () => {
  return (
    <div style={{ minHeight: "100vh", background: "#f3f4f6" }}>
      <PriceSearchPage />
    </div>
  );
};

export default App;