{
  description = "Flake utils demo";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlays.default ];

        };
      in {
        packages = {
          inherit (pkgs) mosaic;
          default = self.packages."${system}".mosaic;
        };
      })) // {

        overlays.default = final: prev: { mosaic = prev.callPackage ./. { }; };
      };
}
