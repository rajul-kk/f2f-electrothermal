# c4 dry, step c (DESIGN.md): one OpenROAD session in G97's image on G99's Ibex with G100's k0 activity. Writes, per
# net, PDNSim's voltages, PDNSim's own network as SPICE, and the raw power-grid geometry for an independent build.
# env: RES, CORNER, VTS (as gates/g96/dry/load_routed.tcl), VCD, VCD_SCOPE, OUT, LOADER (path of load_routed.tcl)
source $::env(LOADER)
read_vcd -scope $::env(VCD_SCOPE) $::env(VCD)
report_power -digits 8
set block [ord::get_db_block]
set tech [ord::get_db_tech]
puts "DBU [$tech getDbUnitsPerMicron]"

# PDNSim's resistance per layer ("Ohm per square" / "Ohm per cut"), printed by its own getResistanceMap
set_debug_level PSM resistance 1

proc via_layers {box} {
  set v [$box getTechVia]
  if {$v eq "NULL"} { set v [$box getBlockVia] }
  return [list $v [[$v getBottomLayer] getName] [[$v getTopLayer] getName]]
}

foreach net {VDD VSS} {
  set n [$block findNet $net]
  puts "NET $net bterms [llength [$n getBTerms]] iterms [llength [$n getITerms]] swires [llength [$n getSWires]]"
  puts "ANALYZE $net:"
  analyze_power_grid -net $net -voltage_file $::env(OUT)/v_$net.csv -error_file $::env(OUT)/err_$net.rpt
  puts "SPICE $net:"
  write_pg_spice -net $net $::env(OUT)/pg_$net.sp

  # geometry: one line per special-wire box; vias with their cut boxes (DBU, absolute)
  set f [open $::env(OUT)/geom_$net.tsv w]
  puts $f "kind\tlayer\txlo\tylo\txhi\tyhi\tvia\tbottom\ttop\tcx\tcy"
  foreach sw [$n getSWires] {
    foreach b [$sw getWires] {
      set r [list [$b xMin] [$b yMin] [$b xMax] [$b yMax]]
      if {[$b isVia]} {
        lassign [via_layers $b] v bot top
        set c [list [expr {([$b xMin] + [$b xMax]) / 2}] [expr {([$b yMin] + [$b yMax]) / 2}]]
        if {![catch {$b getViaXY} xy] && [llength $xy] == 2} { set c $xy }
        puts $f "via\t-\t[join $r \t]\t[$v getName]\t$bot\t$top\t[join $c \t]"
        foreach vb [$v getBoxes] {
          set l [$vb getTechLayer]
          if {$l eq "NULL" || [$l getType] ne "CUT"} { continue }
          puts $f "cut\t[$l getName]\t[expr {[$vb xMin] + [lindex $c 0]}]\t[expr {[$vb yMin] + [lindex $c 1]}]\t[expr {[$vb xMax] + [lindex $c 0]}]\t[expr {[$vb yMax] + [lindex $c 1]}]\t[$v getName]\t$bot\t$top\t[join $c \t]"
        }
      } else {
        puts $f "wire\t[[$b getTechLayer] getName]\t[join $r \t]\t-\t-\t-\t-\t-"
      }
    }
  }
  foreach bt [$n getBTerms] {
    foreach bp [$bt getBPins] {
      foreach bx [$bp getBoxes] {
        puts $f "bterm\t[[$bx getTechLayer] getName]\t[$bx xMin]\t[$bx yMin]\t[$bx xMax]\t[$bx yMax]\t[$bt getName]\t-\t-\t-\t-"
      }
    }
  }
  close $f

  # instance pins on the net: instance, pin, placed, bbox (DBU)
  set f [open $::env(OUT)/iterms_$net.tsv w]
  puts $f "inst\tpin\tplaced\txlo\tylo\txhi\tyhi"
  foreach it [$n getITerms] {
    set i [$it getInst]
    set bb [$it getBBox]
    puts $f "[$i getName]\t[[$it getMTerm] getName]\t[$i isPlaced]\t[$bb xMin]\t[$bb yMin]\t[$bb xMax]\t[$bb yMax]"
  }
  close $f
}

# per-instance power, the input PDNSim divides by VDD (instance, total W)
set f [open $::env(OUT)/inst_power.tsv w]
puts $f "inst\tpower_w"
foreach i [$block getInsts] {
  set p [sta::instance_power [sta::find_instance [$i getName]] [sta::cmd_scene]]
  puts $f "[$i getName]\t[lindex $p 3]"
}
close $f
puts "EXPORT DONE"
