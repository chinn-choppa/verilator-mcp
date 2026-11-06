// Successful OS exit, without verification evidence; Apache-2.0.
module tb_unknown;
    initial begin
        #1;
        $display("Done, but the test did not self-check");
        $finish;
    end
endmodule
