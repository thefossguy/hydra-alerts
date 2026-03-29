let
  nixpkgs = fetchTarball "https://codeload.github.com/NixOS/nixpkgs/tar.gz/refs/heads/nixos-unstable-small";
  pkgs = import nixpkgs { system = builtins.currentSystem; };
  lib = pkgs.lib;
in

pkgs.stdenvNoCC.mkDerivation {
  pname = "hydra-alerts";
  version = "0.1.0";

  src = lib.cleanSource ./.;

  buildInputs = [ pkgs.python3 ];

  dontBuild = true;
  installPhase = ''
    install -Dm777 main.py $out/bin/main.py
    install -Dm444 maintained-derivations-with-hydra-urls.nix $out/bin/maintained-derivations-with-hydra-urls.nix
  '';

  meta.mainProgram = "main.py";
}
