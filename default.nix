{ lib, python3, poetry2nix }:

python3.pkgs.buildPythonApplication rec {
  pname = "mosaic";
  version = "unstable-2023-07-13";
  format = "setuptools";

  src = poetry2nix.cleanPythonSources { src = ./.; };

  propagatedBuildInputs = with python3.pkgs; [ pillow ];

  pythonImportsCheck = [ "mosaic" ];

  meta = with lib; {
    description = "Python script for creating photomosaic images";
    homepage = "https://github.com/nialov/mosaic";
    license = licenses.mit;
    maintainers = with maintainers; [ nialov ];
  };
}
