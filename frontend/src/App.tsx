import { useEffect, useState } from "react";
import Home from "./pages/Home";
import NewHandover from "./pages/NewHandover";
import Review from "./pages/Review";
import Successor from "./pages/Successor";

/** 해시 기반 라우팅: #/ · #/new · #/h/:id · #/s/:token */
function useRoute(): string[] {
  const read = () =>
    window.location.hash.replace(/^#\/?/, "").split("?")[0].split("/").filter(Boolean);
  const [parts, setParts] = useState(read);
  useEffect(() => {
    const onChange = () => {
      setParts(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return parts;
}

export default function App() {
  const [section, param] = useRoute();

  if (section === "s" && param) return <Successor token={param} />;

  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="#/">
          <span className="brand-mark" aria-hidden="true" />
          인수인계 장부
        </a>
        <nav>
          <a href="#/new" className="btn btn-quiet">
            새 인수인계 만들기
          </a>
        </nav>
      </header>
      {section === "new" ? (
        <NewHandover />
      ) : section === "h" && param ? (
        <Review id={Number(param)} />
      ) : (
        <Home />
      )}
    </div>
  );
}
