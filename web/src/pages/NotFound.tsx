import { Compass } from "lucide-react";
import { Link } from "react-router";

import { EmptyState } from "../components/ui";

export default function NotFound() {
  return (
    <EmptyState icon={Compass} title="Page not found">
      <Link to="/" className="text-brand hover:underline">Back to Live Monitor</Link>
    </EmptyState>
  );
}
