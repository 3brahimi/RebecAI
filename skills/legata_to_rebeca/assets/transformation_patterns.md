# Legata→Rebeca Transformation Patterns

## Equipment Range Pattern (Rule 22)

### Legata Structure
```
clause['Equipment Range Check']:{
    condition: { OS.Length > meters(50) }
    assure: {
        : OS.Equipment.MastheadLight.Range >= miles(6)
        : OS.Equipment.SideLight.Range >= miles(3)
    }
}
```

### Rebeca Mapping
```
property {
  define {
    ship_longer_50m = (s1.ship_length > 50);
    masthead_range_ok = (s1.masthead_light_range >= 6);
    sidelight_range_ok = (s1.sidelight_range >= 3);
  }
  Assertion {
    Rule22: !ship_longer_50m || (masthead_range_ok && sidelight_range_ok);
  }
}
```

## Exclude Block Pattern (Rule 23)

### Legata Structure
```
clause['Power Driven Signaling']:{
    condition: { OS.Type is Vessel.Type.PowerDriven }
    exclude: { OS.Length < meters(12) }
    assure: {
        : OS.Signal.ON has 'Light.Masthead'
        : OS.Signal.ON has 'Light.Sidelight'
    }
}
```

### Rebeca Mapping
```
property {
  define {
    isPowerDriven = (s1.vessel_type == PowerDriven);
    isSmallShip = (s1.ship_length < 12);
    lightsOn = (s1.masthead_light_on && s1.sidelight_on);
  }
  Assertion {
    Rule23: !isPowerDriven || isSmallShip || lightsOn;
  }
}
```

## Multi-Actor Pattern

### Rebeca with Multiple Ships
```
property {
  define {
    ship1_lights = (s1.masthead_light_on && s1.sidelight_on);
    ship2_lights = (s2.masthead_light_on && s2.sidelight_on);
    bothSafety = (ship1_lights && ship2_lights);
  }
  Assertion {
    MultiplshipSafety: bothSafety;
  }
}
```

## Temporal Logic Pattern (LTL)

### Liveness Property
```
property {
  define {
    lightsNeeded = (s1.visibility < 500);
    lightsActive = (s1.masthead_light_on);
  }
  LTL {
    Liveness: G(lightsNeeded -> F(lightsActive));
  }
}
```
