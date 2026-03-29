{
  maintainer ? throw ''
    The 'maintainer' argument must be specified. Pass it on the command line:
      nix-build default.nix --argstr maintainer '<maintainer-name>'
  '',
}:

let
  nixpkgs = fetchTarball "https://codeload.github.com/NixOS/nixpkgs/tar.gz/refs/heads/nixos-unstable-small";
  supportedSystems = [
    "aarch64-linux"
    "x86_64-linux"
  ];

  lib = import (nixpkgs + "/lib");

  specifiedMaintainer =
    if !(builtins.hasAttr maintainer lib.maintainers) then
      throw ''
        maintainer '${maintainer}' not found in lib.maintainers
        Make sure the name matches an entry in <nixpkgs/maintainers/maintainer-list.nix>.
      ''
    else
      lib.maintainers."${maintainer}";

  nixpkgsConfig = {
    config = {
      allowAliases = false;
      allowUnfree = true;
      allowBroken = true;
    };
  };

  buildPkgs = import nixpkgs (nixpkgsConfig // { system = builtins.currentSystem; });

  maintainedBy =
    maintainerAttr: attrPath:
    let
      result = builtins.tryEval (builtins.elem maintainerAttr (attrPath.meta.maintainers or [ ]));
    in
    result.success && result.value;

  forSystem =
    system:
    let
      pkgs = import nixpkgs (nixpkgsConfig // { inherit system; });

      packageAttrs = builtins.listToAttrs (
        builtins.concatMap (
          name:
          if maintainedBy specifiedMaintainer pkgs.${name} then
            [
              {
                name = "nixpkgs.${name}.${system}";
                value = "https://hydra.nixos.org/job/nixos/unstable/nixpkgs.${name}.${system}/latest";
              }
            ]
          else
            [ ]
        ) (builtins.attrNames pkgs)
      );

      testAttrs = lib.optionalAttrs pkgs.stdenv.isLinux (
        builtins.listToAttrs (
          builtins.concatMap (
            name:
            if maintainedBy specifiedMaintainer pkgs.nixosTests.${name} then
              [
                {
                  name = "nixos.tests.${name}.${system}";
                  value = "https://hydra.nixos.org/job/nixos/unstable/nixos.tests.${name}.${system}/latest";
                }
              ]
            else
              [ ]
          ) (builtins.attrNames pkgs.nixosTests)
        )
      );

    in
    packageAttrs // testAttrs;

  allAttrs = builtins.foldl' (acc: system: acc // forSystem system) { } supportedSystems;

  content = builtins.toJSON allAttrs;

in

builtins.seq specifiedMaintainer (
  buildPkgs.runCommand "maintainer-attrs" { } ''
    echo -n ${lib.escapeShellArg content} > $out
  ''
)
