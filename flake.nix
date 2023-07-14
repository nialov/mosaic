{
  description = "Flake utils demo";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nix-extra.url = "github:nialov/nix-extra";
  inputs.nixpkgs.follows = "nix-extra/nixpkgs";

  outputs = { self, ... }@inputs:
    (inputs.flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import inputs.nixpkgs {
          inherit system;
          overlays =
            [ self.overlays.default inputs.nix-extra.overlays.default ];

        };
      in {
        packages = {
          inherit (pkgs) mosaic-dev;
          default = self.packages."${system}".mosaic-dev;
        };
        devShells = {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python3Packages.ipython
              python3Packages.pytest
              python3Packages.pytest-regressions
            ];
            inputsFrom = [ self.packages."${system}".mosaic-dev ];
          };
        };
      })) // {

        overlays.default = final: prev: {
          # mosaic-dev = final.mosaic.overrideAttrs (finalAttrs: prevAttrs: {
          #   pname = "mosaic";
          #   version = "unstable-2023-07-13";
          #   format = "pyproject";
          #   src = prev.poetry2nix.cleanPythonSources { src = ./.; };
          #   checkInputs = with prev.python3.pkgs; [ pytestCheckHook pytest ];

          #   pythonImportsCheck = [ "mosaic" ];
          #   propagatedBuildInputs = prevAttrs.propagatedBuildInputs
          #     ++ [ prev.python3Packages.typer ]
          #     ++ prev.python3Packages.typer.passthru.optional-dependencies.all;
          #   nativeBuildInputs = with prev.python3.pkgs; [ setuptools wheel ];
          # });
          mosaic-dev = prev.callPackage ./. { };

        };
      };
}
