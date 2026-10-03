// Is this the public static build (GitHub Pages) rather than the local app (`ags up`)?
// The deploy workflow builds with PUBLIC_HOSTED=1. The public site has no /api server, so it
// skips the local-server probes (no console 404s), hides Sync, and offers Sleeper leagues only:
// ESPN's league API refuses browser requests from other sites and needs the local proxy.
export const hosted: boolean = __HOSTED__;
