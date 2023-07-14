{
  description = "Flake utils demo";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "nixpkgs/nixos-unstable";

  outputs = { self, ... }@inputs:
    (inputs.flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import inputs.nixpkgs {
          inherit system;
          overlays = [ self.overlays.default ];

        };
      in {
        packages = {
          inherit (pkgs) mosaic;
          default = self.packages."${system}".mosaic;
        };
        devShells = {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python3Packages.ipython
              python3Packages.pytest
              python3Packages.pytest-regressions
            ];
            inputsFrom = [ self.packages."${system}".mosaic ];
          };
        };
        checks = { inherit (pkgs) mosaic; };
      })) // {

        overlays.default = final: prev: {
          mosaic = prev.callPackage ./. { };

        };
      };
}
