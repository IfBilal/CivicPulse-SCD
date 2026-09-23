import { Link } from "react-router-dom";

import { DecodeText } from "../components/DecodeText";
import { Glass } from "../components/Glass";

export default function NotFound() {
  return (
    <Glass className="empty" style={{ maxWidth: 560, margin: "60px auto", textAlign: "center" }}>
      <p className="eyebrow" style={{ justifyContent: "center" }}>
        404 · no signal
      </p>
      <h1 className="page-title" style={{ fontSize: 40 }}>
        <DecodeText className="grad" text="Off the grid." />
      </h1>
      <p className="page-sub" style={{ margin: "0 auto 20px" }}>
        This street isn&apos;t on our map.
      </p>
      <Link className="btn btn-primary" to="/">
        Report a problem
      </Link>
    </Glass>
  );
}
