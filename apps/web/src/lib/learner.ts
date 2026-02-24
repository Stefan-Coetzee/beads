import { getLTIContext } from "./lti";

export function getLearnerId(): string | null {
  const lti = getLTIContext();
  return lti?.isLTI ? lti.learnerId : null;
}
